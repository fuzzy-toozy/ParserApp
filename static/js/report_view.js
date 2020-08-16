$(document).ready(
    function() {
fill_table_body();

    });

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function prepare_report_column(column_server_data, add_icons) {
    let popover_msg = "<b>Last scan:</b><br />";
    let icon_class = "";
    let icon_bg = "";
    let report_result = "-";
    let result_col = document.createElement("td");
    result_col.innerHTML = report_result;

    if (!add_icons) {
        return result_col;
    }

    if (column_server_data) {
        let scan_result = escapeHtml(column_server_data["result"]);
        let scan_time = column_server_data["time"];
        popover_msg += scan_time;
        let rescode = column_server_data["rescode"];
        if (rescode == 0x1488) {
            icon_class = "fa fa-check-circle";
            icon_bg = "bg-green";
        } else if (rescode == 0x1487) {
            icon_class = "fa fa-exclamation-triangle";
            icon_bg = "bg-yellow";
            popover_msg += "<br /><b>Warning:</b><br /> " + escapeHtml(column_server_data["error"]);
        } else if (rescode == -50) {
            icon_class = "fa fa-times-circle";
            icon_bg = "bg-purple";
            popover_msg += "Never";
        } else {
            icon_class = "fa fa-exclamation-circle";
            icon_bg = "bg-red";
            popover_msg += "<br /><b>Error:</b><br />" + escapeHtml(column_server_data["error"]);
        }
        if (scan_result) {
            report_result = scan_result;
        }
    } else {
        icon_class = "fa fa-times-circle";
        icon_bg = "bg-purple";
        popover_msg += "Never";
    }
    let result_span = document.createElement("span");
    result_span.innerHTML = report_result;
    result_col.innerHTML = "";
    result_col.appendChild(result_span);
    let col_div_child = document.createElement("div");
    col_div_child.className = "icon-alert " + icon_bg;
    let icon_node = document.createElement("i");
    icon_node.className = icon_class;
    let col_div_icons = document.createElement("div");
    col_div_child.appendChild(icon_node);
    col_div_icons.appendChild(col_div_child);
    col_div_icons.className = "icon-container";
    result_col.appendChild(col_div_icons);
    $(col_div_child).hover(function() {
        $(this).popover({
            content: popover_msg,
            html: true,
            container: "body"
        }).popover('show');
        $(".popover-content").css("word-wrap", "break-word");
    }, function() {
        $(this).popover('hide');
    });

    return result_col;
}

function addUrl(element, url) {
    let div_child = document.createElement("div");
    div_child.className = "icon-href bg-blue";
    let icon_node = document.createElement("i");
    icon_node.className = "fa fa-external-link";
    div_child.appendChild(icon_node);
    div_parent = document.createElement("div");
    div_parent.className = "icon-container";
    div_parent.appendChild(div_child);
    $(div_child).on("click", function() {
        window.open(url);
    });
    $(div_child).hover(function() {
        $(this).popover({
            content: url,
            html: true,
            container: "body"
        }).popover('show');
        $(".popover-content").css("word-wrap", "break-word");
    }, function() {
        $(this).popover('hide');
    });
    element.appendChild(div_parent);
}

function fill_table_body() {
    let view_table_body = document.getElementById("report_view_tbody");
    for (product_name in view_data) {
        let product_name_row = document.createElement("tr");
        let product_name_col = document.createElement("th");
        product_name_col.innerHTML = product_name;
        product_name_col.colSpan = 1000;
        product_name_col.className += "bg-gray";
        product_name_row.appendChild(product_name_col);
        view_table_body.appendChild(product_name_row);
        ass(view_table_body, product_name);
        console.log("Pizdec prosto");
    }
}

function ass(view_table_body, product_name) {
    let base_data = view_data[product_name];
    let product_data = base_data["sellers"];

    let th1 = document.createElement("th")
    th1.innerHTML = "#"

    let thead_row = document.createElement("tr");
    thead_row.appendChild(th1);
    view_table_body.appendChild(thead_row);
    let table_rows = []
    let table_cols = []

    let base_row = document.createElement("tr");
    let base_col = document.createElement("td");
    base_col.innerHTML = "<b>Basic Price</b>";
    base_col.style.cssText = "border-bottom-width: 2px;";
    base_row.appendChild(base_col);

    view_table_body.appendChild(base_row);

    let opt_names = base_data["all_opts"];
    for (let idx = 0; idx < opt_names.length; idx++) {
        let option_row = document.createElement("tr");
        let option_col = document.createElement("td");
        option_col.innerHTML = "<b>" + opt_names[idx] + "</b>";
        option_col.value = opt_names[idx];
        option_row.appendChild(option_col);
        table_rows.push(option_row);
    }

    for (seller_name in product_data) {
        let seller_data = product_data[seller_name];
        let add_icons = seller_data["rescode"] != -100;
        let base_data_col = prepare_report_column(seller_data, add_icons);
        base_data_col.style.cssText = "border-bottom-width: 2px;";
        base_row.appendChild(base_data_col);
        console.log("Kakie zhe hohli degenerati");
        let seller_options = seller_data["options"];

        for (let idx = 0; idx < table_rows.length; idx++) {
            let option_data = seller_options[table_rows[idx].children[0].value];
            table_rows[idx].appendChild(prepare_report_column(option_data, add_icons));
        }
    }

    for (seller_name in product_data) {
        let new_th = document.createElement("th");
        new_th.innerHTML = seller_name;
        addUrl(new_th, product_data[seller_name]["url"])
        thead_row.appendChild(new_th);
    }

    for (let idx = 0; idx < table_rows.length; idx++) {
        view_table_body.appendChild(table_rows[idx]);
    }
}

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
    table_header.appendChild(thead_row);
    let table_rows = []
    let table_cols = []

    let base_row = document.createElement("tr");
    let base_col = document.createElement("td");
    base_col.innerHTML = "<b>BASE</b>";
    base_col.style.cssText = "border-bottom-width: 2px;";
    base_row.appendChild(base_col);

    table_header.appendChild(base_row);
    //tbody.appendChild(base_row);

    let opt_names = base_data["all_opts"];
    for (let idx = 0; idx < opt_names.length; idx++) {
        let option_row = document.createElement("tr");
        let option_col = document.createElement("td");
        option_col.innerHTML = opt_names[idx];
        option_row.appendChild(option_col);
        table_rows.push(option_row);
    }

    for (seller_name in product_data) {
        let seller_data = product_data[seller_name];
        //table_rows[0].appendChild(prepare_report_column(seller_data));
        let add_icons = seller_data["rescode"] != -100;
        let base_data_col = prepare_report_column(seller_data, add_icons);
        base_data_col.style.cssText = "border-bottom-width: 2px;";
        addUrl(base_data_col, seller_data["url"])
        base_row.appendChild(base_data_col);
        console.log(seller_name);
        let seller_options = seller_data["options"];

        for (let idx = 0; idx < table_rows.length; idx++) {
            console.log(table_rows[idx].children[0].innerHTML)
            let option_data = seller_options[table_rows[idx].children[0].innerHTML];
            table_rows[idx].appendChild(prepare_report_column(option_data, add_icons));
        }
    }

    for (seller_name in product_data) {
        let new_th = document.createElement("th");
        new_th.innerHTML = seller_name;
        thead_row.appendChild(new_th);
        let base_seller_col = document.createElement("td");
    }

    new_table.appendChild(table_header);

    for (let idx = 0; idx < table_rows.length; idx++) {
        tbody.appendChild(table_rows[idx]);
    }
    new_table.appendChild(tbody);
    new_table.className = "table table-bordered table-stripped table-sm nowrap";
    let report_table_id = "ReportData_" + product_name;
    new_table.setAttribute("id", report_table_id);
    new_table.setAttribute("width", "100%");
    return new_table;
}
