function prettify_json(json_string) {
if (! json_string) {
    return "";
}
    let removed_whites = json_string.trim()//json_string.replace(/\s/g,'');
if (removed_whites) {
    removed_whites = removed_whites.replace(/^"/,'');
    removed_whites = removed_whites.replace(/"$/,'');
    console.log(removed_whites);
    var obj = JSON.parse(removed_whites);
    var pretty = JSON.stringify(obj, undefined, 4);
    return pretty;
    }
    return "";
}

function format_parser_parameters() {
    var option_parser_areas = document.querySelectorAll('*[id^="option_parser_parameters"]');
    for (let i = 0; i < option_parser_areas.length; ++i) {
        let current_area = option_parser_areas[i];
        let text_to_format = current_area.value;
        current_area.textContent = prettify_json(text_to_format);
    }

    var base_parser_param = document.getElementById("basic_parser_parameters");
    let text_to_format = base_parser_param.value;
    base_parser_param.textContent = prettify_json(text_to_format);
}

function format_url() {
    var url_area = document.getElementById("monitor_url");
    var url_text = url_area.value;
    if (url_text) {
        url_area.value = url_text.replace(/\s/g,'');
    } else {
        url_area.value = "";
    }

}

function setup_parser_options_maxlength() {
    var option_parser_selectors = document.querySelectorAll('*[id^="select_option"]');
    for (let i = 0; i < option_parser_selectors.length; ++i) {
        setup_option_maxlength(option_parser_selectors[i].id);
    }
}

$(document).ready(function() {
    setup_option_maxlength("select_base_parser");
    setup_parser_options_maxlength();
    document.querySelectorAll('*[id^="select_option"]');

    format_parser_parameters();
    format_url();

    $(".searchable_dropdown").select2({
        placeholder: "Select parser",
    });
});

function check_error(input_text, option_id, parent_container) {
    var errmsg = document.getElementById("errmsg" + option_id);
    try {
        var js = JSON.parse(input_text);
    } catch (ex) {
        if (! errmsg) {
            errmsg = document.createElement("span");
            errmsg.id = "errmsg" + option_id;
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

function save_monitoring_object(project_id, monitoring_id, product_id, seller_id, redirect_url)
{

    var basic_parser_select = document.getElementById("select_base_parser");
    var basic_parser_id = basic_parser_select.options[basic_parser_select.selectedIndex].value;
    var basic_parser_params = document.getElementById("basic_parser_parameters").value;

    if (basic_parser_params && basic_parser_params.length > 0) {
        if (check_error(basic_parser_params, "basic", document.getElementById("basic_params_cont")) == -1) {
            return;
        }
    }

    var option_parser_selectors = document.querySelectorAll('*[id^="select_option"]');
    var monitor_url = document.getElementById("monitor_url").value;

    var options_data = [];
    var parser_data = {
                        "options": options_data,
                        "seller_id": seller_id,
                        "product_id": product_id,
                        "monitoring_id": monitoring_id,
                        "project_id": project_id,
                        "basic_parser": { "id": basic_parser_id, "params": basic_parser_params },
                        "monitor_url": monitor_url
                      };

    for (let i = 0; i < option_parser_selectors.length; ++i) {
        parser_select = option_parser_selectors[i];
        let option_id = parser_select.getAttribute("value");
        let parser_id = parser_select.options[parser_select.selectedIndex].value;
        let option_param_text_area = document.getElementById("option_parser_parameters" + option_id);
        let parser_params = option_param_text_area.value;

        if (parser_params && parser_params.length > 0) {
            if (check_error(parser_params, option_id, document.getElementById("option_params" + option_id)) == -1) {
                return;
            }
        }

        options_data.push(
        { "option_id": option_id,
          "parser_id": parser_id,
          "params": parser_params
        });
    }

    $.ajax({
        type: 'POST',
        url: '/save_monitoring_object',
        cache: false,
        processData: false,
        data: JSON.stringify(parser_data),
        contentType: "application/json",
        success: function (data) {
            window.location.href = redirect_url;
        },
        error: function (error_message) {
        }
    })
}
