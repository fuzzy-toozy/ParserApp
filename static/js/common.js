function submit_form(form_to_submit) {
    form_to_submit.submit();
}

function submit_parser_stuff(form_to_submit) {
    check_error();
    check_error(basic_parser_params, "basic", document.getElementById("basic_params_cont"))
}

function remove_entity(project_id, common_name, entity_id, entity_name, post_url, redirect_url)
{
    if (! confirm('Delete ' + common_name + ' ' + entity_name + '?')) {
        return;
    }

    var project_data = JSON.stringify({
            "id": entity_id,
            "project_id": project_id
        })

    $.ajax({
        type: 'POST',
        url: post_url,
        cache: false,
        processData: false,
        data: project_data,
        contentType: "application/json",
        success: function (data) {
            window.location.href = redirect_url
        },
        error: function (error_message) {
        }
    })
}

var maxLength = 40;

function shorten_text(text_string) {
    if (text_string.length > maxLength) {
        return text_string.substr(0, maxLength) + '...';
    }

    return text_string
}

function setup_option_maxlength(node_id) {
$('#' + node_id + ' > option').text(function(i, text) {
    return shorten_text(text);
});
}

function setup_text_maxlength(node_id) {
$('#' + node_id).text(function(i, text) {
    return shorten_text(text);
});
}
