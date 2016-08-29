var queryOutput;

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
                    $('#permalink').attr('href', location.origin+'/'+data['filename']);
                    $('#permalink').prop('hidden', false);
                    location.pathname = '/'+data['filename'];
                    
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

function setVisCode(){
    window["visualize"] = new Function($("#javascript").val());
}