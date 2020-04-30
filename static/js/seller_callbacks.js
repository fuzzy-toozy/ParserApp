function remove_seller(project_id, seller_id, seller_name, post_url)
{
    if (! confirm('Delete seller ' + seller_name + '?')) {
        return;
    }

    var project_data = JSON.stringify({
            "id": seller_id,
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
            window.location.href = '/sellers_view/' + project_id
        },
        error: function (error_message) {
        }
    })
}
