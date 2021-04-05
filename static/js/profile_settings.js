$(document).ready(function() {
    set_smtp_settings();
    let smtp_form = document.getElementById("smtp_settings");

    for (input_el of smtp_form.elements) {
        $(input_el).click(function () {
            $(this).popover("destroy");
        });

        $(input_el).on("input", function () {
            this.style.borderColor = "";
            $(this).popover("destroy");
        });
    }
});

function set_smtp_settings() {
    if (smtp_settings) {
        let smtp_port = document.getElementById("smtp_port");
        smtp_port.value = Number.parseInt(smtp_settings["port"]);

        let smtp_server = document.getElementById("smtp_addr");
        smtp_server.value = smtp_settings["address"];

        let smtp_mailbox = document.getElementById("smtp_login");
        smtp_mailbox.value = smtp_settings["mailbox"];

        let smtp_password = document.getElementById("smtp_pwd");
        smtp_password.value = smtp_settings["password"];
    }
}

$("#profileImage").click(function(e) {
    $("#imageUpload").click();
});

function fasterPreview( uploader ) {
    if ( uploader.files && uploader.files[0] ){
          $('#profileImage').attr('src',
             window.URL.createObjectURL(uploader.files[0]) );
    }
}

$("#imageUpload").change(function(){
    fasterPreview( this );
});


function save_user_profile(save_url, redirect_url)
{
    var options_table = document.getElementById("options_data_table")
    var table_json = tableToJSON(options_table)
    var options_data = {"deleted": deleted_options, "rest": table_json};
    var user_name = document.getElementById("user-name-form").value;

    let smtp_form = document.getElementById("smtp_settings");

    let smtp_data = {};
    for (smtp_el of smtp_form.elements) {
        smtp_data[smtp_el.name] = smtp_el.value;
    }

    let form_data = new FormData($('#profile-settings-form')[0]);
    form_data.append("parameters", JSON.stringify({"name": user_name, "emails": options_data, "smtp": smtp_data}));

    $.ajax({
        type: "POST",
        url: save_url,
        cache: false,
        processData: false,
        data: form_data,
        contentType: false,
        success: function (data) {
            window.location.href = redirect_url
        },
        error: function (error_message) {
            console.log(error_message)
        }
    })
}

function edit_row_wrap(no)
{
    let $edit_form = $(edit_row(no));
    $edit_form.validator().on("invalid.bs.validator", function (event) {
    $(this).popover({
            trigger: "manual",
            placement: 'bottom',
            content: function() { return event.detail; },
            html: false,
            container: "body"
        }).popover('show');
        $(".popover-content").css("word-wrap", "break-word");
    });

    $edit_form.validator().on("valid.bs.validator", function (event) {
        let input_text = this.elements[0].value;
        if (input_text.length == 0) {
            let event = $.Event('invalid.bs.validator', { relatedTarget: $(this), detail: "Field can't be empty" });
            this.elements[0].parentNode.className = "form-group has-error has-danger";
            $(this).trigger(event);

            return;
        }
        save_row(no);
    });

    $edit_form.click(function() {
        $(this).popover("destroy");
    });

    $edit_form.on("input", function() {
        this.elements[0].parentNode.className = "form-group";
        $(this).popover("destroy");
    });
}

function save_row_wrap(no)
{
    let $edit_node = $(document.getElementById("option_name_form" + no));
    $edit_node.validator("validate");
}


$("#new_mail_form").validator().on("valid.bs.validator", function (event) {
    let input_text = this.elements[0].value;
    if (input_text.length == 0) {
        let event = $.Event('invalid.bs.validator', { relatedTarget: $(this), detail: "Field can't be empty" });
        this.elements[0].parentNode.className = "form-group has-error has-danger";
        $(this).trigger(event);

        return;
    }
    add_row(edit_row_wrap, save_row_wrap);
});

$("#new_mail_form").click(function () {
  $(this).popover("destroy");
});

$("#new_mail_form").on("input", function () {
    this.elements[0].parentNode.className = "form-group";
    $(this).popover("destroy");
});

$("#new_mail_form").validator().on("invalid.bs.validator", function (event) {
    $(this).popover({
            trigger: "manual",
            placement: 'bottom',
            content: function() { return event.detail; },
            html: false,
            container: "body"
        }).popover('show');
        $(".popover-content").css("word-wrap", "break-word");
})

function validate_password(input_id, current) {
    let pwd_first = document.getElementById(input_id).value;
    let err_msg = document.getElementById("pwd_check");
    let err_msg_txt = document.getElementById("err_msg_txt");
    pwd_is_valid = false;
    if (pwd_first.length == 0 || pwd_first.localeCompare(current.value) != 0) {
        err_msg.className = "fa fa-exclamation-triangle bg-red round-corners"
        if (pwd_first.length == 0 && current.value.length == 0) {
            err_msg_txt.innerHTML = "Password can't be empty";
        } else {
            err_msg_txt.innerHTML = "Password doesn't match";
        }
    } else {
        err_msg.className = "fa fa-check bg-green round-corners";
        pwd_is_valid = true;
        err_msg_txt.innerHTML = "";
    }

    err_msg.style.display = "";

    return pwd_is_valid;
}

$("#password_text1").on("input", function () {
    validate_password("password_text2", this);
});

$("#password_text2").on("input", function () {
    validate_password("password_text1", this);
});

$('#smtp_settings').on('keyup keypress', function(e) {
  var keyCode = e.keyCode || e.which;
  if (keyCode === 13) {
    e.preventDefault();
    return false;
  }
});

function save_password(save_pwd_url)
{
    let show_message = function (success, msg) {
        let err_msg_txt = document.getElementById("err_msg_txt");
        err_msg_txt.innerHTML = msg;
        let err_msg = document.getElementById("pwd_check");
        if (success) {
            err_msg.className = "fa fa-check bg-green round-corners";
        } else {
            err_msg.className = "fa fa-exclamation-triangle bg-red round-corners"
        }
    };

    let pwd_field = document.getElementById("password_text1");
    if (validate_password("password_text2", pwd_field)) {
        let ucp_data = JSON.stringify({ "ucp": pwd_field.value });
        $.ajax({
            type: 'POST',
            url: save_pwd_url,
            cache: false,
            processData: false,
            data: ucp_data,
            contentType: "application/json",
            success: function (data) {
                show_message(true, "Password saved successfully");
            },
            error: function (error_message) {
                show_message(false, "Failed to save password");
                console.log(error_message);
            }
        });
    }
}

function pwd_toggle(elements)
{
    for (el of elements) {
        let temp = document.getElementById(el);
        if (temp.type === "password") {
            temp.type = "text";
        } else {
            temp.type = "password";
        }
    }
}

function add_row_valid()
{
    $('#new_mail_form').validator("validate");
}

function get_back(main_url)
{
    if (document.referrer) {
        window.location = document.referrer;
    } else {
        window.location = main_url;
    }
}

function error_empty() {
    let smtp_form = document.getElementById("smtp_settings");
    let has_errors = false;
    for (input_el of smtp_form.elements) {
        if (input_el.value.length == 0) {
            input_el.style.borderColor = "#dd4b39";
            $(input_el).popover({
                trigger: "manual",
                placement: 'bottom',
                content: "Field can't be empty",
                html: false,
                container: "body"
            }).popover('show');
            $(".popover-content").css("word-wrap", "break-word");
            has_errors = true;
        }
    }
    return has_errors;
}

$("#smtp_port").on("input", function() {
    if (this.value > 65535) {
        this.value = 65535;
    } else if (this.value < 1) {
        this.value = 1;
    }
});

function check_smtp_connection()
{
    if (error_empty())  {
        return;
    }
    let form = $("#smtp_settings");
    let url = form.attr("action");

    let show_message = function (success, msg, popover_text) {
        let err_msg_txt = document.getElementById("conn_err_msg_txt");
        err_msg_txt.innerHTML = msg;
        let err_msg = document.getElementById("connection_check");
        if (success) {
            err_msg.className = "fa fa-check bg-green round-corners";
            err_msg.style.display = "";
            $(err_msg).popover("destroy");
        } else {
            err_msg.className = "fa fa-exclamation-triangle bg-red round-corners"
            err_msg.style.display = "";
        }

        if (popover_text) {
            $(err_msg).popover("destroy");
            $(err_msg).popover({
                trigger: "hover",
                placement: 'top',
                content: popover_text,
                html: false,
                container: "body"
            });
            $(".popover-content").css("word-wrap", "break-word");
        }
    };

    let err_msg = document.getElementById("connection_check");
    err_msg.className = "fa fa-exclamation-triangle bg-yellow round-corners"
    err_msg.style.display = "";
    let err_msg_txt = document.getElementById("conn_err_msg_txt");
    err_msg_txt.innerHTML = "Checking...";
    $.ajax({
           type: "POST",
           url: url,
           data: form.serialize(),
           success: function(data)
           {
               show_message(true, "Connection successful", "");
           },
           error: function(xhr, status, error) {
                show_message(false, "Connection failed", xhr.responseText);
           }
         });
}
