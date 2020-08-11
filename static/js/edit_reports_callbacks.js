let change_callback = function(){};

function set_monitored_objects(view_data) {
        let set_selected_monitorings = function () {
            let view_objects = view_data["objects"];
            let select_nodes = $('[id^="seller_select_"]');
             for (let idx = 0; idx < select_nodes.length; ++idx) {
                let select_node = select_nodes[idx];
                let selected_vals = [];
                $("#" + select_node.id + " option").each(function() {
                    if (Number(this.value) in view_objects) {
                        selected_vals.push(this.value);
                    }
                });
                $(select_node).val(selected_vals).trigger("change");
            }
        };

        change_callback = set_selected_monitorings;
        $("#monitoring_select").val(view_data["monitoring"]).trigger("change");
}


function set_timepicker(timestamp) {
    $('#datetime_input').val(timestamp);
}

function set_days_of_week(days_data) {
    let days_checkboxes = $('[id^="day_of_week"]');
    for (let idx = 0; idx < days_checkboxes.length; idx++) {
        let day_checkbox = days_checkboxes[idx];

        if ( days_data.indexOf(Number(day_checkbox.value)) > -1 ) {
            day_checkbox.checked = true;
        }
    }
}

function set_report_name(report_name) {
    document.getElementById("report_name_input").value = report_name;
}

function set_notifications_enable_flag(is_enabled) {
     document.getElementById("report_enabled_input").checked = is_enabled;
}

$(document).ready(function() {
    $('.select2').select2();
    $('#datetime_input').datetimepicker({format:'HH:mm UTC'});

    if (view_data) {
        set_monitored_objects(view_data);
        set_timepicker(view_data["timestamp"]);
        set_days_of_week(view_data["days"]);
        set_report_name(view_data["name"]);
        set_notifications_enable_flag(view_data["notify"]);
    }
});

function monitoring_changed(selected_option, post_url)
{
    let data_to_send = {"monitoring_id": selected_option.value};
    let complete_url = post_url + selected_option.value;
    console.log(complete_url);
    $.ajax({
        type: 'POST',
        url: post_url + selected_option.value,
        cache: false,
        processData: false,
        data: data_to_send,
        contentType: "application/json",
        dataType: "html",
        success: function (data) {
            let box_element = document.getElementById("monitoring_objects_box_body");
            $(box_element).html(data);
            $('.select2').select2();
            change_callback();
        },
        error: function (error_message) {
            console.log(error_message);
        }
    })
}

function save_report()
{
    let monitored_objects = $('[id^="seller_select_"]');
    let monitored_objects_data = {};

    for (let idx = 0; idx < monitored_objects.length; ++idx) {
        let seller_select_node = monitored_objects[idx];
        let seller_id = seller_select_node.getAttribute("seller_id");
        let selected_values = $(seller_select_node).find(":selected");

        let monitored_objects_ids = [];
        for(let sel_idx = 0; sel_idx < selected_values.length; ++sel_idx) {
            let selected_value = selected_values[sel_idx];
            monitored_objects_ids.push(Number(selected_value.getAttribute("monitored_object_id")));
        }

        if (monitored_objects_ids.length > 0) {
            monitored_objects_data[seller_id] = monitored_objects_ids;
        }
    }

    let days_checkboxes = $('[id^="day_of_week"]');
    let checked_days = [];
    for (let idx = 0; idx < days_checkboxes.length; idx++) {
        let day_checkbox = days_checkboxes[idx];
        if (day_checkbox.checked) {
            checked_days.push(Number(day_checkbox.getAttribute("value")));
        }
    }

    let report_data_object = {};
    report_data_object["monitoring_objects"] = monitored_objects_data;
    report_data_object["days"] = checked_days;

    let report_epoch_timestamp = $('#datetime_input').val();//Number(moment($('#datetime_input').val()[-3]).utc().valueOf());
    console.log(report_epoch_timestamp);
    let report_enabled = document.getElementById("report_enabled_input").checked;
    let report_name = document.getElementById("report_name_input").value;
    let monitoring_id = document.getElementById("monitoring_select").value;

    report_data_object["utc_epoch"] = report_epoch_timestamp;
    report_data_object["email_enabled"] = report_enabled;
    report_data_object["name"] = report_name;

    report_data_object["project_id"] = project_id;
    report_data_object["entity_id"] = entity_id;
    report_data_object["monitoring_id"] = monitoring_id;

    $.ajax({
        type: 'POST',
        url: save_url,
        cache: false,
        processData: false,
        data: JSON.stringify(report_data_object),
        contentType: "application/json",
        success: function (data) {
            window.location.href = redirect_url;
        },
        error: function (error_message) {
            console.log(error_message);
        }
    })
}
