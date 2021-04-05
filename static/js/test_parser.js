function submit_form_check_js(form_to_submit) {
    var input_text = document.getElementById("parser_parameter").value;
    if (input_text && check_js_error(input_text, "parser_parameter_error", document.getElementById("text_container")) == -1) {
        return;
    }
    form_to_submit.submit();
}

function check_js_error(input_text, err_label_id, parent_container) {
    var errmsg = document.getElementById(err_label_id);
    try {
        var js = JSON.parse(input_text);
    } catch (ex) {
        if (! errmsg) {
            errmsg = document.createElement("span");
            errmsg.id = err_label_id;
            errmsg.style.color = "red";
            parent_container.appendChild(errmsg);
        }

        errmsg.textContent = ex.message;
        return -1;
    }

    if (errmsg) {
        errmsg.textContent = "";
    }

    return 0;
}
