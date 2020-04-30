/* Formatting function for row details - modify as you need */
var shitctr = 0;
function set_row_child ( row ) {
var ret;
$.ajax({
   url:"/sellers_table_data/1/1/2",
   type:'GET',
   dataType: 'html',
   success: function(data){
        let row_data = row.child(data);
        row_data.show();
        var rowtbl = $("#" + data_id).DataTable();
   }
});
}

on_expand_product(table_id, data_id) {
    var table = $("#" + table_id).DataTable();
    var tr = $(this).closest('tr');
    var row = table.row( tr );

    if ( row.child.isShown() ) {
        row.child.hide();
        tr.removeClass('shown');
    }
    else {
        set_row_child(row, data_id);
        tr.addClass('shown');
    }
}

$(document).ready(function() {
    var table = $('#example').DataTable();

    // Add event listener for opening and closing details
    $('#gay1').on('click', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );

        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // Open this row
            set_row_child(row);
            tr.addClass('shown');
            var rowtbl = $("#gaystuff1").DataTable();
        }
    } );
} );
