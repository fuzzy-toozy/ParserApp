import flask
import json
import smtplib

from flask_login import login_required, current_user
from flask import Blueprint

from common.reports import send_reports

from database.users import session_scope
from database.models import User, UserEmail, SmtpSettings
from database.database import flask_db

settings = Blueprint("settings", __name__)


@settings.route("/settings", methods=['GET'])
@login_required
def profile_settings():
    save_settings_url = flask.url_for("settings.save_profile_settings")
    avatar_url = flask.url_for("settings.user_avatar")
    redirect_url = flask.url_for("projects.main_form")
    save_pwd_url = flask.url_for("settings.save_password")
    with session_scope(True) as session:
        current_user_db = flask_db.session.query(User).filter(User.username == current_user.username).first()
        stored_emails_db = session.query(UserEmail).filter(UserEmail.user_id == current_user_db.id).all()
        smtp_settings_db = session.query(SmtpSettings).filter(SmtpSettings.user_id == current_user_db.id).first()

        smtp_data = dict()
        if smtp_settings_db is not None:
            smtp_data["port"] = smtp_settings_db.port
            smtp_data["address"] = smtp_settings_db.address
            smtp_data["mailbox"] = smtp_settings_db.mailbox
            smtp_data["password"] = smtp_settings_db.password

    return flask.render_template("settings/profile_settings.html",
                                 save_url=save_settings_url,
                                 redirect_url=redirect_url,
                                 avatar_url=avatar_url,
                                 user_emails=stored_emails_db,
                                 save_pwd_url=save_pwd_url,
                                 smtp_settings=smtp_data)


@settings.route("/save_settings", methods=['POST'])
@login_required
def save_profile_settings():
    form_params = json.loads(flask.request.form.get("parameters"))
    user_emails = form_params["emails"]
    new_name = form_params["name"]
    smtp_settings = form_params["smtp"]

    uploaded_image = flask.request.files.get("profile_photo")

    if uploaded_image is not None:
        uploaded_image = uploaded_image.read()

    current_user_db = flask_db.session.query(User).filter(User.username == current_user.username).first()

    if uploaded_image:
        current_user_db.avatar = uploaded_image

    if new_name != current_user_db.username:
        current_user_db.username = new_name

    with session_scope() as session:
        smtp_settings_db = session.query(SmtpSettings).filter(SmtpSettings.user_id == current_user_db.id).first()

        if smtp_settings_db is None:
            session.add(SmtpSettings(user_id=current_user_db.id,
                                     port=smtp_settings["port"],
                                     address=smtp_settings["address"],
                                     mailbox=smtp_settings["mailbox"],
                                     password=smtp_settings["password"]))
        else:
            smtp_settings_db.port = smtp_settings["port"]
            smtp_settings_db.address = smtp_settings["address"]
            smtp_settings_db.mailbox = smtp_settings["mailbox"]
            smtp_settings_db.password = smtp_settings["password"]

        stored_emails_db = session.query(UserEmail).filter(UserEmail.user_id == current_user_db.id).all()

        id_to_option_stored = {}
        stored_options_set = set()

        for option in stored_emails_db:
            id_to_option_stored[option.id] = option
            stored_options_set.add(option.id)

        id_to_option_received = {}
        received_existing_options_set = set()
        options_to_insert = []
        for option_name, option_id in user_emails['rest']:
            if int(option_id) != -1:
                received_existing_options_set.add(int(option_id))
                id_to_option_received[int(option_id)] = option_name
            else:
                options_to_insert.append(option_name)

        options_to_update = received_existing_options_set.intersection(stored_options_set)

        print(options_to_update)

        for option_id in options_to_update:
            user_mail = session.query(UserEmail).filter(UserEmail.id == option_id).first()
            if user_mail and user_mail.email != id_to_option_received[option_id]:
                session.query(UserEmail).filter(UserEmail.id == option_id).delete()
            else:
                continue
            new_option = UserEmail(email=id_to_option_received[option_id], user_id=current_user_db.id)
            session.add(new_option)

        for option_id in user_emails["deleted"]:
            session.query(UserEmail).filter(UserEmail.id == int(option_id)).delete()

        for option_name in options_to_insert:
            new_option = UserEmail(email=option_name, user_id=current_user_db.id)
            session.add(new_option)

    return "OK"


@settings.route('/save_password', methods=['POST'])
@login_required
def save_password():
    pwd = flask.request.get_json()["ucp"]
    user = User.query.filter(User.id == int(current_user.get_id())).first()
    print(pwd)
    user.set_password(pwd)
    return "OK"


@settings.route('/user_avatar')
@login_required
def user_avatar():
    current_user_db = flask_db.session.query(User).filter(User.username == current_user.username).first()

    if current_user_db.avatar is None:
        with open("static/images/rambie.jpg", "rb") as avatar_file:
            user_avatar = avatar_file.read()
    else:
        user_avatar = current_user_db.avatar

    response = flask.make_response(user_avatar)
    response.headers.set("Content-Type", "image/jpeg")
    response.headers.set("Content-Disposition", "inline", filename="%s.jpg" % current_user_db.username)
    return response


def check_smtp_connection(smtp_form):
    smtp_server_port = smtp_form.get("port")
    smtp_server_address = smtp_form.get("address")
    smtp_mailbox = smtp_form.get("mailbox")
    smtp_mailbox_password = smtp_form.get("password")

    bad_request = 400
    if not smtp_server_port or int(smtp_server_port) < 1 or int(smtp_server_port) > 65535:
        return flask.Response("Invalid SMTP server port", status=bad_request)
    if not smtp_server_address:
        return flask.Response("Invalid SMTP server address", status=bad_request)
    if not smtp_mailbox:
        return flask.Response("Invalid SMTP mailbox", status=bad_request)
    if not smtp_mailbox_password:
        return flask.Response("Invalid SMTP mailbox password", status=bad_request)

    try:
        smtp_server_address = flask.request.form.get("address")
        smtp_server_port = int(flask.request.form.get("port"))
        smtp_mailbox = flask.request.form.get("mailbox")
        smtp_mailbox_password = flask.request.form.get("password")

        mailserver = smtplib.SMTP_SSL(smtp_server_address, smtp_server_port)
        mailserver.login(smtp_mailbox, smtp_mailbox_password)
        mailserver.quit()
    except Exception as ex:
        return flask.Response(str(ex), status=bad_request)

    return "OK"


@settings.route('/test_smtp_connection', methods=['POST'])
@login_required
def test_smtp_connection():
    return check_smtp_connection(flask.request.form)

@settings.route('/send_shit', methods=['GET'])
@login_required
def send_shit():
    send_reports()
    return "OPK"

