from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import os
import requests
import shutil
import subprocess
import sys
import CloudFlare
import traceback

from django.conf import settings
from django.core.cache import cache
from django.dispatch import receiver
from django.db.models.signals import pre_delete, post_delete, post_save

from mlarchive.archive.models import Message, EmailList

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Signal Handlers
# --------------------------------------------------

@receiver([post_save, post_delete], sender=EmailList)
def _clear_lists_cache(sender, instance, **kwargs):
    """If EmailList object is saved or deleted remove the list_info cache entry
    """
    cache.delete('lists')
    cache.delete('lists_public')


@receiver(pre_delete, sender=Message)
def _message_remove(sender, instance, **kwargs):
    """When messages are removed, via the admin page, we need to move the message
    archive file to the "_removed" directory and purge the cache
    """
    path = instance.get_file_path()
    if not os.path.exists(path):
        return
    target_dir = instance.get_removed_dir()
    if not os.path.exists(target_dir):
        os.mkdir(target_dir)
        os.chmod(target_dir, 02777)
    target_path = os.path.join(target_dir, os.path.basename(path))
    if os.path.exists(target_path):
        os.remove(path)
    else:
        shutil.move(path, target_dir)

    logger.info('message file moved: {} => {}'.format(path, target_dir))

    # if message is first of many in thread, should reset thread.first before
    # deleting
    if (instance.thread.first == instance and
            instance.thread.message_set.count() > 1):
        next_in_thread = instance.thread.message_set.order_by('date')[1]
        instance.thread.set_first(next_in_thread)

    # handle cache
    if settings.SERVER_MODE == 'production' and settings.USING_CDN:
        purge_files_from_cache(instance)


@receiver(post_save, sender=Message)
def _update_thread(sender, instance, **kwargs):
    """When messages are saved, udpate thread info
    """
    if not instance.thread.first or instance.date < instance.thread.date:
        instance.thread.set_first(instance)


@receiver(post_save, sender=Message)
def _purge_cache(sender, instance, created, **kwargs):
    if created and settings.SERVER_MODE == 'production' and settings.USING_CDN:
        purge_files_from_cache(instance)


@receiver(post_save, sender=EmailList)
def _list_save_handler(sender, instance, **kwargs):
    # _flush_noauth_cache(instance)
    _export_lists()


# --------------------------------------------------
# Helpers
# --------------------------------------------------


def get_purge_cache_urls(message, created=True):
    """Retuns a list of absolute urls to purge from cache when message
    is created or deleted
    """
    # all messages in thread
    if created:
        urls = [m.get_absolute_url_with_host() for m in message.thread.message_set.all().exclude(pk=message.pk)]
    else:
        urls = [m.get_absolute_url_with_host() for m in message.thread.message_set.all()]
    # previous and next by date
    next_in_list = message.next_in_list()
    if next_in_list:
        urls.append(next_in_list.get_absolute_url_with_host())
    previous_in_list = message.previous_in_list()
    if previous_in_list:
        urls.append(previous_in_list.get_absolute_url_with_host())
    # index pages
    urls.extend(message.get_absolute_static_index_urls())
    # dedupe
    urls = list(set(urls))
    return urls


def purge_files_from_cache(message, created=True):
    """Purge file from Cloudflare cache"""
    urls = get_purge_cache_urls(message, created)
    with CloudFlare.CloudFlare(email=settings.CLOUDFLARE_AUTH_EMAIL, token=settings.CLOUDFLARE_AUTH_KEY) as cf:
        try:
            cf.zones.purge_cache.post(settings.CLOUDFLARE_ZONE_ID, data={'files': urls})
            logger.info('purging cached urls for list {}'.format(message.email_list.name))
            logger.debug('purging cached urls: {}'.format(urls))
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            traceback.print_exc(file=sys.stdout)
            logger.error(e)
        except requests.exceptions.HTTPError as e:
            logger.error(e)


def _export_lists():
    """Write XML dump of list / memberships and call external program"""

    # Dump XML
    data = _get_lists_as_xml()
    path = os.path.join(settings.EXPORT_DIR, 'email_lists.xml')
    try:
        if not os.path.exists(settings.EXPORT_DIR):
            os.mkdir(settings.EXPORT_DIR)
        with open(path, 'w') as file:
            file.write(data)
            os.chmod(path, 0666)
    except Exception as error:
        logger.error('Error creating export file: {}'.format(error))
        return

    # Call external script
    if hasattr(settings, 'NOTIFY_LIST_CHANGE_COMMAND'):
        command = settings.NOTIFY_LIST_CHANGE_COMMAND
        try:
            subprocess.check_call([command, path])
        except (OSError, subprocess.CalledProcessError) as error:
            logger.error('Error calling external command: {} ({})'.format(command, error))


def _flush_noauth_cache(email_list):
    keys = ['{:04d}-noauth'.format(user.id) for user in email_list.members.all()]
    cache.delete_many(keys)


def _get_lists_as_xml():
    """Returns string: XML of lists / membership for IMAP"""
    lines = []
    lines.append("<ms_config>")

    for elist in EmailList.objects.all().order_by('name'):
        lines.append("  <shared_root name='{name}' path='/var/isode/ms/shared/{name}'>".format(name=elist.name))
        if elist.private:
            lines.append("    <user name='anonymous' access='none'/>")
            for member in elist.members.all():
                lines.append("    <user name='{name}' access='read,write'/>".format(name=member.username))
        else:
            lines.append("    <user name='anonymous' access='read'/>")
            lines.append("    <group name='anyone' access='read,write'/>")
        lines.append("  </shared_root>")
    lines.append("</ms_config>")
    return "\n".join(lines)