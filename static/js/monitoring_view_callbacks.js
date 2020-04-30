function set_row_child (row, data_url, data_id) {
var ret;
$.ajax({
   url: data_url,
   type:'GET',
   dataType: 'html',
   success: function(data){
        setup_row(row, data, data_id);
   }
});
}

function setup_row(row, data, id) {
        let row_data = row.child(data);
        row_data.show();
        var rowtbl = $("#" + id).DataTable();
}

function on_expand_product(cur_td, table_id, data_id, ajax_url) {
    var table = $("#" + table_id).DataTable();
    var tr = $(cur_td).closest('tr');
    var row = table.row( tr );

    if ( row.child.isShown() ) {
        row.child.hide();
        tr.removeClass('shown');
    } else {
        set_row_child(row, ajax_url, data_id);
        tr.addClass('shown');
    }
}

$(document).ready(function() {
    var sellers_table = $('#monitored_products').DataTable({"scrollX": true});
});

function remove_mon_object(project_id, mon_id, sel_id, prod_id, prod_name, sel_name , post_url, redirect_url)
{
    if (! confirm('Delete monitoring object for product "' + prod_name + ' and seller "' + sel_name + '"?')) {
        return;
    }

    var project_data = JSON.stringify({
            "monitoring_id": mon_id,
            "seller_id": sel_id,
            "product_id": prod_id,
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
