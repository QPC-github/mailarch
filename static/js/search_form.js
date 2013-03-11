/* search_form.js */

$(function() {
    jQuery.substitute = function(str, sub) {
        return str.replace(/\{(.+?)\}/g, function($0, $1) {
            return $1 in sub ? sub[$1] : $0;
        });
    };

    function build_query(ev) {
        var query_string="";
        //var part_pattern="{param}:({keyword})";
        //var not_pattern="-{param}:({keyword})";
        var part_pattern="{param}:{keyword}";
        var not_pattern="-{param}:{keyword}";
        
        var op_value=$('#id_operator').val();
        
        // regular query fields'
        var operands=new Array();
        $('.query_chunk').each(function() {
            if($(this).children('input').val()!=''){
                var obj={
                    param:$(this).children('select').val(),
                    keyword:$(this).children('input').val()
                };
                operands.push(jQuery.substitute(part_pattern,obj))
            }
        });
        query_string += operands.join(' '+op_value+' ');
        
        // not feilds
        var not_operands=new Array();
        $('.not_chunk').each(function() {
            if($(this).children('input').val()!=''){
                obj={
                    param:$(this).children('select').val(),
                    keyword:$(this).children('input').val()
                };
                not_operands.push(jQuery.substitute(not_pattern,obj))
            }
        });
        if(not_operands.length>0) {
            if(query_string!='')query_string+=' ';
            query_string+=not_operands.join(' ');
        }
        
        $('#id_q').val(query_string);
        
    }
    
    function increment_ids(el) {
        var from = $(el).attr('id').split('_')[2];
        var to = parseInt(from)+1;
        var old_id = $(el).attr("id");
        // increment div id
        $(el).attr("id", old_id.replace(from, to));
        // increment input ids
        $(el).children().each(function(i,e){
            var old_name = $(e).attr('name');
            var old_id = $(e).attr('id');
            $(e).attr('name', old_name.replace(from, to));
            $(e).attr('id', old_id.replace(from, to));
        })
    }
    
    function init() {
        // bind build_query() to change events
        $('#id_query-0-value').focus().bind('change keyup',build_query);
        $('#id_query-0-field').change(build_query);
        $('#id_not-0-value').bind('change keyup',build_query);
        $('#id_not-0-field').change(build_query);
        
        $('a.remove_btn').click(function() {
            var remove_index = $(this).attr('id').split('_')[1];
            $('div#query_chunk_' + remove_index).remove()
            if ($('.query_chunk').length == 1) {
                $('.query_chunk:first').removeClass('removable');
            }
            build_query();
        });
        
        $('a.not_remove_btn').click(function() {
            var remove_index = $(this).attr('id').split('_')[2];
            //alert(remove_index);
            $('div#not_chunk_' + remove_index).remove()
            if ($('.not_chunk').length == 1) {
                $('.not_chunk:first').removeClass('removable');
            }
        });
        
        $('#add_query_part').click(function() {        
            $('.query_chunk:first').addClass('removable');
            var count = $('.query_chunk').length;
            var cloned = $('.query_chunk').last().clone(true);
            var last = $('.query_chunk:last');
            cloned.children('input').val('');
            cloned.insertAfter(last);
            increment_ids($('.query_chunk').last(), $('.query_chunk').length-1);;
        });
        
        $('#add_not_part').click(function() {        
            $('.not_chunk:first').addClass('removable');
            var cloned = $('.not_chunk').last().clone(true);
            var last = $('.not_chunk:last');
            cloned.children('input').val('');
            cloned.insertAfter(last);
            increment_ids($('.not_chunk').last());;
        });
    }
    
    init();

});