function on_list_click(list_id) {
  let dropdn_list = document.getElementById(list_id)
  dropdn_list.classList.add("show");
}

$(document).ready(function() {
    $(".searchable_dropdown_seller").select2({
        placeholder: "Select seller",
    });

    $(".searchable_dropdown_product").select2({
        placeholder: "Select product",
    });

    $(".common_dropdown_scan_interval").select2({
        minimumResultsForSearch: -1
    });

    $(".common_dropdown_request_interval").select2({
        minimumResultsForSearch: -1
    });

    let $mon_sellers_select = $("#monitoring_sellers_select");
    $mon_sellers_select.select2({
        placeholder: "Add seller",
    });
    let seller_change_fired = false;
    $mon_sellers_select.on("change", function() {
        if (! seller_change_fired) {
            seller_change_fired = true;
            let $selected = $(this).find(":selected");
            on_list_element_click_dt("seller", null, $selected.val(), $selected.text());
            $(this).val(null).trigger("change");
        } else {
            seller_change_fired = false;
        }
    });

    let $mon_products_select = $("#monitoring_products_select");
    $mon_products_select.select2({
        placeholder: "Add product",
    });
    let product_change_fired = false;
    $mon_products_select.on("change", function() {
        if (! product_change_fired) {
            product_change_fired = true;
            let $selected = $(this).find(':selected');
            on_list_element_click_dt("product", null, $selected.val(), $selected.text());
            $(this).val(null).trigger("change");
        } else {
            product_change_fired = false;
        }
    });

});


function on_list_element_click(entity_name, element, entity_id, entity_name_concrete) {
    var dropdowns = document.getElementById(entity_name + "_list_view");
    if (document.getElementById(entity_name + "_tablerow_" + entity_id)) {
        dropdowns.classList.remove('show');
        return;
    }
    var table_body_name = "chosen_" + entity_name + "s_table_body"
    var table = document.getElementById("chosen_" + entity_name + "s_table");
    var table_body = document.getElementById("chosen_" + entity_name + "s_table_body");
    var table_len = (table.rows.length)-1;
    var row = table_body.insertRow(table_len).outerHTML =
    "<tr id='" + entity_name + "_tablerow_" + entity_id + "'>" +
    "<td id='" + entity_name + "_name" + table_len + "'>" + entity_name_concrete + "</td>" +
    "<td id='remove_" + entity_name + table_len + "' class='remove_chosen_" + entity_name + "' " +
    "onclick=remove_from_table(" + table_body_name + "," + entity_id + ")></td>" +
    "</tr>"
    dropdowns.classList.remove('show');
}

let added_entities = { "product": added_products, "seller": added_sellers };
function on_list_element_click_dt(entity_name, element, entity_id, entity_name_concrete) {
    let added = added_entities[entity_name];
    if (! added.hasOwnProperty(entity_id) ) {
        added[entity_id] = entity_name_concrete;
    } else {
        return;
    }
    var table_id = "#chosen_" + entity_name + "s_table";
    var table = $(table_id).DataTable();

    var table_api = $(table_id).dataTable().api();
    var rowCount = table_api.rows({page: 'current'}).count();

    var row_element = document.createElement("tr");
    row_element.id = entity_name + "_tablerow_" + entity_id;
    row_element.setAttribute("value", entity_id);

    var column_1 = document.createElement("td");
    column_1.id = entity_name + "_name" + rowCount;
    column_1.textContent = shorten_text(entity_name_concrete);

    var column_2 = document.createElement("td");
    column_2.id = "remove_" + entity_name + rowCount;
    column_2.onclick = remove_from_table.bind(table, row_element);
    column_2.classList.add("remove_chosen");

    row_element.appendChild(column_1);
    row_element.appendChild(column_2);

    table.row.add(row_element).draw(false);
}

function setup_table_text_maxlength() {
    var seller_table_cols = document.querySelectorAll('*[id^="seller_name"]');
    for (let i = 0; i < seller_table_cols.length; ++i) {
        added_entities[setup_text_maxlength(seller_table_cols[i].id)];
    }
}

function fillEmptyRows() {
      var api = this.api();
      var rowCount = api.rows({page: 'current'}).count();

      for (var i = 0; i < api.page.len() - (rowCount === 0? 1 : rowCount); i++) {
        $('#' + this.attr('id') + ' tbody').append($("<tr><td>&nbsp;</td><td></td></tr>"));
      }
}

function remove_first_opt(clicked) {
    console.log(clicked)
}

function remove_from_table(table_row_el) {
    this.row(table_row_el).remove().draw(false);
    delete added_entities[$(table_row_el.cells[0]).attr("id").split("_")[0]][Number($(table_row_el).attr("value"))];
}

function setup_remove_buttons(table) {
    var table_rows = table.rows().nodes();
    for(let idx = 0; idx < table_rows.length; idx++) {
        table_rows[idx].cells[1].onclick = remove_from_table.bind(table, table_rows[idx]);
    }
}

$(document).ready(function() {
    var sellers_table = $('#chosen_sellers_table').DataTable( { drawCallback: fillEmptyRows, "pagingType": "full" } );
    var products_table = $('#chosen_products_table').DataTable( { drawCallback: fillEmptyRows, "pagingType": "full" } );

    setup_remove_buttons(sellers_table);
    setup_remove_buttons(products_table);


    setup_option_maxlength("seller_self");
    setup_table_text_maxlength();
});

function get_ids(table_id)
{
    var table = $(table_id).DataTable();
    var data_array = table.rows().nodes();

    var id_array = []
    for(let idx = 0; idx < data_array.length; idx++) {
        id_array.push({ "id": data_array[idx].getAttribute('value'), "name": data_array[idx].cells[0].innerHTML });
    }

    return id_array;
}

function save_monitoring_data(save_data_url, redirect_url, project_id, monitoring_id)
{
    var products_array = get_ids("#chosen_products_table");
    var sellers_array = get_ids("#chosen_sellers_table");

    var seller_self = document.getElementById("seller_self");
    var selected_seller_self = seller_self.options[seller_self.selectedIndex].value;

    var update_interval = document.getElementById("update_interval");
    var selected_update_interval = update_interval.options[update_interval.selectedIndex].value;

    var request_interval = document.getElementById("request_interval");
    var selected_request_interval = request_interval.options[request_interval.selectedIndex].value;

    var parser_name_input = document.getElementById("monitoring_name_input");
    var parser_name = parser_name_input.value;

    var monitoring_enabled = document.getElementById("monitoring_enabled_input").checked;

    var serialised_data = { "products" : products_array,
                            "sellers": sellers_array,
                            "name": parser_name,
                            "update_interval": selected_update_interval,
                            "request_interval": selected_request_interval,
                            "seller_self": selected_seller_self,
                            "monitoring": monitoring_id,
                            "project": project_id,
                            "enabled": monitoring_enabled
                          };

    $.ajax({
        type: 'POST',
        url: save_data_url,
        cache: false,
        processData: false,
        data: JSON.stringify(serialised_data),
        contentType: "application/json",
        success: function (data) {
            window.location.href = redirect_url
        },
        error: function (error_message) {
            console.log(error_message);
        }
    })
}

function post_force_scan(post_url) {
        $.ajax({
        type: 'POST',
        url: post_url,
        cache: false,
        processData: false,
        data: "",
        contentType: "application/json",
        success: function (data) {
            alert("Scan started successfully");
        },
        error: function (error_message) {
            alert(error_message);
        }
    });
}
