function run_code(){
    var runsql = $('#run-sql').prop('checked');
    var runjs = $('#run-js').prop('checked');
    
    if(runsql){
		$('#run-button').prop('disabled',false);
        
        $.ajax({
            url: '/runcode',
            type: 'post',
            data: {'query':$('#sql').val()},
            dataType: 'html',
            success: function(response) {
                $('#run-button').prop('disabled',false);
                // console.log(response);
                $('#query-output').children().remove();
                
                if(response[0] === '<'){
                    $('#query-output').append($(response));
                } else {
                    $('#query-output').append($('<pre class="error">'+response+'</pre>'));
                }
            },
            failure: function(response) {
                $('#run-button').prop('disabled',false);
                // console.log(response);
                $('#query-output').append($('<p>Something went wrong! :(</p>'));
            }
        });
    }
}

// From https://docs.djangoproject.com/en/1.9/ref/csrf/
// using jQuery
// function getCookie(name) {
    // var cookieValue = null;
    // if (document.cookie && document.cookie !== '') {
        // var cookies = document.cookie.split(';');
        // for (var i = 0; i < cookies.length; i++) {
            // var cookie = jQuery.trim(cookies[i]);
            // // Does this cookie string begin with the name we want?
            // if (cookie.substring(0, name.length + 1) === (name + '=')) {
                // cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                // break;
            // }
        // }
    // }
    // return cookieValue;
// }
// var csrftoken = getCookie('csrftoken');
// function csrfSafeMethod(method) {
    // // these HTTP methods do not require CSRF protection
    // return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
// }
// $.ajaxSetup({
    // beforeSend: function(xhr, settings) {
        // if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            // xhr.setRequestHeader("X-CSRFToken", csrftoken);
        // }
    // }
// });