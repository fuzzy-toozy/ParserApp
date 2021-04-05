var deleted_options = [];

function edit_row(no)
{
 document.getElementById("option_edit_button"+no).classList.add("hidden");
 document.getElementById("option_save_button"+no).classList.remove("hidden");

 var name = document.getElementById("option_name_row"+no);

 var name_data = name.getAttribute("value");
 var edit_node = document.createElement("input");

 edit_node.type = "email";
 edit_node.id = "option_name_text" + no;
 edit_node.classList.add("form-control", "align-middle");
 edit_node.setAttribute("value", name_data);
 edit_node.setAttribute("spellcheck", "false");
 name.innerHTML = "";

 let form_element = document.createElement("form");
 let form_div = document.createElement("div");
 form_div.classList.add("form-group");
 form_element.id = "option_name_form" + no;

 form_div.appendChild(edit_node);
 form_element.appendChild(form_div);
 name.appendChild(form_element);

 return form_element;
}

function save_row(no)
{
 let option_name = document.getElementById("option_name_text"+no);
 let option_form = document.getElementById("option_name_form"+no);

 let name_col_node = document.getElementById("option_name_row"+no);
 name_col_node.removeChild(option_form);
 name_col_node.innerHTML = option_name.value;
 name_col_node.setAttribute("value", option_name.value);

 document.getElementById("option_edit_button"+no).classList.remove("hidden");
 document.getElementById("option_save_button"+no).classList.add("hidden");
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

function create_button(b_id, b_class, b_text, b_click, b_icon, t_len) {
    let btn = document.createElement("a");
    btn.id = b_id;
    btn.classList.add("edit", "btn", "btn-app");
    btn.onclick = function () { b_click(t_len); };
    let icon_edit = document.createElement("i");
    icon_edit.classList.add("fa", b_icon);
    btn.appendChild(icon_edit);
    btn.innerHTML += b_text;

    return btn;
}

function add_row(edit_func, save_func)
{
 var option_new_name_node = document.getElementById("option_new_name")
 var new_option_name = option_new_name_node.value;

 var table=document.getElementById("options_data_table");
 var table_len=(table.rows.length)-1;

 var table_option_name_col = document.createElement("td");
 var table_buttons_col = document.createElement("td");

 var edit_button = create_button("option_edit_button" + table_len, "edit", "Edit", edit_func, "fa-cogs", table_len);
 var save_button = create_button("option_save_button" + table_len, "save", "Save", save_func, "fa-cogs", table_len);
 var delete_button = create_button("option_delete_button" + table_len, "delete", "Delete", delete_row, "fa-cogs", table_len);

 save_button.classList.add("hidden");

 table_option_name_col.id= "option_name_row" + table_len;
 table_option_name_col.innerHTML = new_option_name;
 table_option_name_col.setAttribute("value", new_option_name);

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
    var product_name = document.getElementById("product_name_input").value;

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
    if (confirm('Delete product ' + product_name + '?')) {
        $.ajax({
            type: 'POST',
            url: '/delete_product',
            cache: false,
            processData: false,
            data: JSON.stringify({ "project_id": project_id, "product_id": product_id}),
            contentType: "application/json",
            success: function (data) {
                window.location.href = '/products_view/' + project_id
            },
            // Ошибка http
            error: function (error_message) {
            }
         })
    }
}

function tableToJSON(table) {
  var obj = [];
  var row, rows = table.rows;
  for (var i=1, iLen=rows.length - 1; i<iLen; i++) {
    row = rows[i];
      obj.push([row.cells[0].getAttribute("value"), row.getAttribute("value")]);
  }
  return obj;
}
