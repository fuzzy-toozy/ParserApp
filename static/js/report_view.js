$(document).ready(
function() {
console.log(view_data);
    var table = $('#report_data').DataTable(
    {
      "columns": [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {}],
      "order": [[1, 'asc']]
    });

    $('#report_data tbody').on('click touch', 'td.details-control', function () {
    let tr = $(this).closest('tr');
    var row = table.row( tr );
    if ( row.child.isShown() ) {
        row.child.hide();
        tr.removeClass('shown');
    } else {
        let new_table = format(row.data());
        row.child( new_table ).show();
        $(new_table).DataTable({
                'paging'      : false,
                'searching'   : false,
                'ordering'    : true,
                'scrollX'     : true,
                'order': [[0, 'desc']],
                });

        tr.addClass('shown');
    }
    });

});

function format(row_data) {
    let product_name = row_data[1]
    let base_data = view_data[product_name];
    let product_data = base_data["sellers"];
    let row = document.createElement("tr");
    let new_table = document.createElement("table");
    let table_header = document.createElement("thead")

    let th1 = document.createElement("th")
    th1.innerHTML = "#"

    let tbody = document.createElement("tbody");
    let thead_row = document.createElement("tr");
    thead_row.appendChild(th1);

    let table_rows = []
    let table_cols = []

    let base_row = document.createElement("tr");
    let base_col = document.createElement("td");
    base_col.innerHTML = "Base";
    base_row.appendChild(base_col);

    table_rows.push(base_row);

    let opt_names = base_data["all_opts"];
    for (option_name in opt_names) {
        let option_row = document.createElement("tr");
        let option_col = document.createElement("td");
        option_col.innerHTML = option_name;
        option_row.appendChild(option_col);
        table_rows.push(option_row);
    }

    for (seller_name in product_data) {
        let seller_data = product_data[seller_name];
        let seller_result = seller_data["result"];
        if (seller_data["rescode"] != 0x1488) {
            seller_result = seller_data["error"];
        }

        let seller_base_col = document.createElement("td");
        seller_base_col.innerHTML = seller_result;
        table_rows[0].appendChild(seller_base_col);
        let seller_options = product_data[seller_name]["options"];

        for (let idx = 1; idx < table_rows.length; idx++) {
            console.log(table_rows[idx].children[0].innerHTML)
            let option_data = seller_options[table_rows[idx].children[0].innerHTML];
            if (option_data) {
                var option_result = option_data["result"];
                if (option_data["rescode"] != 0x1488) {
                    option_result = option_data["error"];
                }
            }
            let option_col = document.createElement("th");
            option_col.innerHTML = option_result;
            table_rows[idx].appendChild(option_col);
        }
    }

    for (seller_name in product_data) {
        let new_th = document.createElement("th");
        new_th.innerHTML = seller_name;
        thead_row.appendChild(new_th);
        let base_seller_col = document.createElement("td");
    }

    table_header.appendChild(thead_row);

    new_table.appendChild(tbody);

    for (let idx = 0; idx < table_rows.length; idx++) {
        table_header.appendChild(table_rows[idx]);
    }

    new_table.appendChild(table_header);
    new_table.className = "table table-bordered";
    return new_table;
}
