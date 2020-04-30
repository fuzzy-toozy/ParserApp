var form_has_valid_data = false;



function remove_entity(project_id, common_name, entity_id, entity_name, post_url, redirect_url)
{
    if (! confirm('Delete ' + common_name + ' ' + entity_name + '?')) {
        return;
    }

    var project_data = JSON.stringify({
            "id": entity_id,
            "project_id": project_id
        })

    $.ajax({
        type: 'POST',
        url: post_url,
        cache: false,
        processData: false,
        data: project_data,
        contentType: "application/json",
        success: function (data) {
            window.location.href = redirect_url + project_id
        },
        error: function (error_message) {
        }
    })
}


function click_upload_btn()
{
        form_has_valid_data = false;
        // Обнуляем поля с сообщениями об ошибках и форму с файлом
        document.getElementById('file-parse-failure-msg').innerText = "";

        $('input[id=parser-file-input]').trigger('change');
        $('input[id=parser-file-input]').trigger('click');
}

function input_form_change(form)
{
        // Достаем файл из формы
        let form_data = new FormData($('#upload-parser')[0]);

        // Получаем объект формы в которую пишем ошибки
        let file_check_text_label = document.getElementById('file-parse-failure-msg');

        // Получаем объект кнопки выбора файла
        let upload_spec_btn = document.getElementById("upload-parser-btn");

        console.log(form.value)

        // Если в форме есть файл
        if (form.value) {
            // Меняем текст на кнопке
            upload_spec_btn.textContent = "File chosen: " + form.value.split('\\').pop();
            // Есть файл для отправки на сервер
            form_has_valid_data = true;
        }
        else {
            // В форме файла нет, возвращаем как было
            upload_spec_btn.textContent = "Chose file";
            form_has_valid_data = false;
            return;
        }

        // Примерно 2мб, для спеки конечно много, но мало ли. Файлы размером больше загружаться не будут.
        let file_max_size = 2097152;
        let uploaded_file_size = form.files[0].size;
        if(uploaded_file_size > file_max_size) {
            // Пишем в форму для ошибок красным цветом и выходим
            file_check_text_label.style.color = "red";
            file_check_text_label.innerText = "Parser file size too large";
            form_has_valid_data = false;
            return;
        }
}

function save_parser_data(post_url, redirect_url)
{
        let file_check_text_label = document.getElementById('file-parse-failure-msg');
        let parser_name_input =  document.getElementById('parser-name-input');
        let parser_name = parser_name_input.value;

        if (parser_name == null || parser_name == "") {
            file_check_text_label.innerText = "Parser name is empty";
            return;
        }

        let form_data = new FormData($('#upload-parser')[0]);
        form_data.append("parameters", JSON.stringify({ "name": parser_name }));

            $.ajax({
            type: 'POST',
            url: post_url,
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                let json_response = JSON.parse(JSON.stringify(data))
                let response_result = json_response["result"];
                let response_message = json_response["message"];

                if (response_result == "ERROR") {
                    file_check_text_label.style.color = "red";
                    file_check_text_label.innerText = response_message;
                }
                else if (response_result == "OK") {
                    window.location.href = redirect_url
                }
                else {
                    file_check_text_label.style.color = "red";
                    file_check_text_label.innerText = "Unknown server response"
                    console.log(JSON.stringify(data))
                }
            },
            // Ошибка http
            error: function (jqXHR, except) {
                    var msg = '';
                    if (jqXHR.status === 0) {
                        msg = 'Not connect.\n Verify Network.';
                    } else if (jqXHR.status == 404) {
                        msg = 'Requested page not found. [404]';
                    } else if (jqXHR.status == 500) {
                         msg = 'Internal Server Error [500].';
                    } else if (exception === 'parsererror') {
                        msg = 'Requested JSON parse failed.';
                    } else if (exception === 'timeout') {
                        msg = 'Time out error.';
                    } else if (exception === 'abort') {
                        msg = 'Ajax request aborted.';
                    } else {
                         msg = 'Uncaught Error.\n' + jqXHR.responseText;
                    }
                    console.log(msg);
                    file_check_text_label.style.color = "red";
                    file_check_text_label.innerText = msg;
            }
        })
}
