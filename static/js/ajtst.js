$(function() {
    $('#lolkek1488').on('click', function() {

            // Все хорошо, формируем запрос на сервер
    $.ajax({
            type: 'POST',
            url: '/check_ajax', // Endpoint, обработчик определен в server.py
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                $("body").html(data);
            },
            // Ошибка http
            error: function (error_message) {
            }
    })
    })
});

$(function() {
    $('#save_project').on('click', function() {
        var form = document.getElementById("project_name_form");
        form.submit();
    })
});

$(function() {
    $('#save_project_settings').on('click', function() {
        var form = document.getElementById("project_settings_name_form");
        form.submit();
    })
});

function remove_project(caller) {
    var project_name = caller.getAttribute('name')
    if (confirm('Delete project ' + caller.getAttribute('name') + '?')) {
        $.ajax({
            type: 'POST',
            url: '/delete_project', // Endpoint, обработчик определен в server.py
            cache: false,
            processData: false,
            data: JSON.stringify({name: project_name}),
            contentType: "application/json",
            success: function (data) {
                $("body").html(data);
            },
            // Ошибка http
            error: function (error_message) {
            }
         })
    }
}

$(document).ready(function() {
    // Setup - add a text input to each footer cell
    /*$('#example tfoot th').each( function () {
        var title = $(this).text();
            $(this).html( '<input type="text" placeholder="Search '+title+'" />' );
    } );*/

    // DataTable
    var table = $('#example').DataTable({
      "scrollX": true,
      "columns": [
            null,
            { "searchable": false },
       ]});

    // Apply the search
    /*table.columns().every( function () {
        var that = this;

        $( 'input', this.footer() ).on( 'keyup change clear', function () {
            if ( that.search() !== this.value ) {
                that
                    .search( this.value )
                    .draw();
            }
        } );
    } );*/
} );
