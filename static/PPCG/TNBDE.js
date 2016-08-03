function run_code(){
    var runsql = $('#run-sql').prop('checked');
    var runjs = $('#run-js').prop('checked');
    
    if(runsql){
		$('#run-button').prop('disabled',false);
        
        $.ajax({
            url: '/runcode',
            type: 'post',
            data: {'query':$('#sql').val(), 'javascript':$('#javascript').val()},
            dataType: 'html',
            success: function(response) {
                $('#run-button').prop('disabled',false);
                $('#query-output').children().remove();
                
                var code = response.slice(0,10); //10 is how long the filename is, server-side
                response = response.slice(10);
                
                if(response[0] === '<'){
                    $('#query-output').append($(response));
                    $('#permalink').attr('href', location.origin+'/'+code);
                    $('#permalink').prop('hidden', false);
                } else {
                    $('#query-output').append($('<pre class="error">'+response+'</pre>'));
                }
            },
            failure: function(response) {
                $('#run-button').prop('disabled',false);
                $('#query-output').append($('<p>Something went wrong! :(</p>'));
            }
        });
    }
}