var deleted_options = [];

function edit_row(no)
{
 document.getElementById("option_edit_button"+no).style.display="none";
 document.getElementById("option_save_button"+no).style.display="inline";

 var name = document.getElementById("option_name_row"+no);

 var name_data = name.getAttribute("value");
 var edit_node = document.createElement("input");

 edit_node.type = "text";
 edit_node.id = "option_name_text" + no;
 edit_node.setAttribute("value", name_data);
 name.innerHTML = "";
 name.appendChild(edit_node);
}

function save_row(no)
{
 var option_name=document.getElementById("option_name_text"+no);

 var name_col_node = document.getElementById("option_name_row"+no);
 name_col_node.removeChild(option_name);
 name_col_node.innerHTML = option_name.value;
 name_col_node.setAttribute("value", option_name.value);

 document.getElementById("option_edit_button"+no).style.display="inline";
 document.getElementById("option_save_button"+no).style.display="none";
}

function delete_row(no)
{
 var table_row = document.getElementById("option_table_row"+no+"");
 var value = table_row.getAttribute("value");
 if (value != "-1") {
    deleted_options.push(value);
 }
 table_row.outerHTML="";
}

function add_row()
{
 var option_new_name_node = document.getElementById("option_new_name")
 var new_option_name = option_new_name_node.value;

 var table=document.getElementById("options_data_table");
 var table_len=(table.rows.length)-1;

 var table_option_name_col = document.createElement("td");
 var table_buttons_col = document.createElement("td");

 var edit_button = document.createElement("input");
 var save_button = document.createElement("input");
 var delete_button = document.createElement("input");

 table_option_name_col.id= "option_name_row" + table_len;
 table_option_name_col.innerHTML = new_option_name;
 table_option_name_col.setAttribute("value", new_option_name);

 edit_button.id = "option_edit_button" + table_len;
 edit_button.value = "Edit";
 edit_button.class = "edit";
 edit_button.onclick = function () { edit_row(table_len); };
 edit_button.type = "button";

 save_button.id = "option_save_button" + table_len;
 save_button.class = "save";
 save_button.value = "Save";
 save_button.onclick = function () { save_row(table_len); };
 save_button.style.display="none";
 save_button.type = "button";

 delete_button.value = "Delete";
 delete_button.class = "delete";
 delete_button.onclick = function () { delete_row(table_len); };
 delete_button.type = "button";

 table_buttons_col.appendChild(edit_button);
 table_buttons_col.appendChild(save_button);
 table_buttons_col.appendChild(delete_button);

 var table_row = table.insertRow(table_len);
 table_row.id = "option_table_row" + table_len;
 table_row.setAttribute("value", "-1");

 table_row.appendChild(table_option_name_col);
 table_row.appendChild(table_buttons_col);

 option_new_name_node.value="";
}

function edit_product_name()
{
    document.getElementById("prodname_edit_button").style.display = "none"
    document.getElementById("prodname_save_button").style.display = "inline"
    var product_name_cont = document.getElementById("product_name")
    var product_name = product_name_cont.innerHTML
    product_name_cont.innerHTML = "<input type='text' id='product_name_text' value='"+product_name+"'>";
}

function save_product_name()
{
    var product_name_cont = document.getElementById("product_name");
    var product_name = document.getElementById("product_name_text").value;
    product_name_cont.innerHTML = product_name;
    product_name_cont.setAttribute("value", product_name);
    document.getElementById("prodname_edit_button").style.display = "inline";
    document.getElementById("prodname_save_button").style.display = "none";
}

function save_current_product(project_id, product_id)
{
    var options_table = document.getElementById("options_data_table")
    var table_json = tableToJSON(options_table)
    var options_data = {"deleted": deleted_options, "rest": table_json};
    var product_name = document.getElementById("product_name").getAttribute("value");

    var project_data = JSON.stringify({
        "project_id": project_id,
        "product_id": product_id,
        "name": product_name,
        "options": options_data })

    $.ajax({
        type: 'POST',
        url: '/save_product',
        cache: false,
        processData: false,
        data: project_data,
        contentType: "application/json",
        success: function (data) {
            window.location.href = '/products_view/'+project_id
        },
        error: function (error_message) {
        }
    })
}

function remove_product(project_id, product_id, product_name) {
    if (confirm('Delete project ' + product_name + '?')) {
        $.ajax({
            type: 'POST',
            url: '/delete_product',
            cache: false,
            processData: false,
            data: JSON.stringify({ "project_id": project_id, "product_id": product_id}),
            contentType: "application/json",
            success: function (data) {
                window.location.href = '/products_view/'+project_id
            },
            // Ошибка http
            error: function (error_message) {
            }
         })
    }
}

function tableToJSON(table) {
  var obj = {};
  var row, rows = table.rows;
  for (var i=1, iLen=rows.length - 1; i<iLen; i++) {
    row = rows[i];
    obj[row.cells[0].getAttribute("value")] = row.getAttribute("value");
  }
  return obj;
}
