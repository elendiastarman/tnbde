var queryOutput;

$(function(){
    fetch_code();
});

function run_code(){
    var runsql = $('#run-sql').prop('checked');
    var runjs = $('#run-js').prop('checked');
    
    if(runsql){
		$('#run-button').prop('disabled',true);
        $('#qout').html("Query output: <em>running...</em>");
        
        $.ajax({
            url: '/runcode',
            type: 'post',
            data: {'query':$('#sql').val(), 'javascript':$('#javascript').val()},
            dataType: 'html',
            success: function(response) {
                $('#run-button').prop('disabled',false);
                $('#query-output').children().remove();
                $('#qout').html("Query output: <em>done!</em>");
                
                var data = JSON.parse(response);
                error = data['error']
                
                if(error === ''){
                    $('#query-output').append($(data['results_html']));
                    sorttable.makeSortable(document.getElementById('query-table'));
                    
                    if(location.pathname.substring(0,7) !== '/tnbde/') {
                        location.pathname = '/tnbde/#'+data['filename'];
                    } else {
                        location.hash = '#'+data['filename'];
                    }
                    
                    $('#permalink').attr('href', location.href);
                    $('#permalink').prop('hidden', false);
                    
                    queryOutput = JSON.parse(data['results_json']);
                    
                    if(runjs){ Function($("#javascript").val())(); }
                } else {
                    $('#query-output').append($('<pre class="error">'+data['error']+'</pre>'));
                }
            },
            failure: function(response) {
                $('#run-button').prop('disabled',false);
                $('#query-output').append($('<p>Something went wrong! :(</p>'));
            }
        });
    } else if(runjs){
        Function($("#javascript").val())();
    }
}

function fetch_code(){
    if(location.hash){
        $.ajax({
            url: '/tnbde/fetch/'+location.hash.substring(1),
            type: 'get',
            data: {},
            dataType: 'html',
            success: function(response) {
                var data = JSON.parse(response);
                error = data['error']
                
                if(!error){
                    $('#sql').val(data['sql'].substring(1));
                    $('#js').val(data['js'].substring(1));
                    
                    run_code();
                } else {
                    $('#permalink-error').prop('hidden', false);
                }
            },
            failure: function(response) {
                $('#permalink-error').prop('hidden', false);
            }
        });
    } else {
        if(location.pathname.substring(0,7) !== '/tnbde/'){ location.hash = '#'+location.pathname.substring(1); location.pathname = '/tnbde/'; }
    }
}

function setVisCode(){
    window["visualize"] = new Function($("#javascript").val());
}