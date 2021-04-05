import json
import smtplib
import logging
import traceback
import time

from signal import signal, SIGINT, SIGTERM, SIG_IGN
from multiprocessing import Process, Event
from sqlalchemy import and_
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from threading import Thread

from datetime import datetime

from routes.reports.routes import DAY_TO_ID, get_report_view_data
from server import server as main_module
from database.users import session_scope
from database.models import ScanReport, SmtpSettings, UserEmail, ReportStat


log = logging.getLogger(__name__)


def smtp_settings_valid(smtp_settings):
    return smtp_settings and smtp_settings.address \
           and smtp_settings.mailbox and smtp_settings.port and smtp_settings.mailbox


def get_smtp_connection(smtp_settings):
    mailserver = smtplib.SMTP_SSL(smtp_settings.address, smtp_settings.port)
    mailserver.login(smtp_settings.mailbox, smtp_settings.password)
    return mailserver


def get_reports_to_send(reports):
    checked_time = datetime.utcnow().strftime("%Y %m %d %H:%M %A")
    current_datetime = checked_time.split()
    reports_to_send = []

    for report in reports:
        if report.days_of_week is None or report.report_time is None:
            continue

        days_of_week_list = json.loads(report.days_of_week)
        current_day_id = DAY_TO_ID[current_datetime[-1]]

        if current_day_id not in days_of_week_list:
            continue

        chours, cminutes = current_datetime[-2].split(":")
        chours = int(chours)
        cminutes = int(cminutes)

        rhours, rminutes = report.report_time.split()[0].split(":")
        rhours = int(rhours)
        rminutes = int(rminutes)

        if chours != rhours:
            continue

        if cminutes != rminutes:
            continue

        reports_to_send.append(report)

    return reports_to_send, checked_time


def get_time_int(time_s):
    shours, sminutes = time_s.split(":")
    shours = int(shours)
    sminutes = int(sminutes)
    return shours, sminutes


def compare_time_now(comp_time, checked_time):
    year1, month1, day_nb1, time1, day_of_week1 = comp_time.split()
    year2, month2, day_nb2, time2, day_of_week2 = checked_time.split()

    return year1 == year2 and month1 == month2 and day_nb1 == day_nb2 and time1 == time2 and day_of_week1 == day_of_week2


def fill_model_object(model_object, model_class, session, **kwargs):
    if model_object:
        for key, val in kwargs.items():
            setattr(model_object, key, val)
    else:
        session.add(model_class(**kwargs))


def send_reports(jinja_env):
    with session_scope(True) as session:
        all_enabled_reports = session.query(ScanReport).filter(ScanReport.notifications_enabled == True).all()

        if len(all_enabled_reports) == 0:
            return

        all_smtp_settings = session.query(SmtpSettings).all()

        settings_to_mails = []

        for smtp_setting in all_smtp_settings:
            user_mails_db = session.query(UserEmail).filter(UserEmail.user_id == smtp_setting.user_id).all()
            user_mails_list = []
            for user_mail in user_mails_db:
                if user_mail is not None:
                    user_mails_list.append(user_mail.email)
            settings_to_mails.append((smtp_setting, user_mails_list))

        unix_time = time.time()
        reports_to_send, checked_time = get_reports_to_send(all_enabled_reports)

        if len(reports_to_send) == 0:
            return

    for smtp_settings, user_mails in settings_to_mails:
        if not smtp_settings_valid(smtp_settings) or len(user_mails) == 0:
            log.debug("SMTP settings are invvalid or user mails are not set")
            continue

        err_msg = None

        try:
            smtp_connection = get_smtp_connection(smtp_settings)
        except Exception as ex:
            tb = traceback.format_exc()
            log.debug(tb)
            err_msg = "Server connection failed: %s" % str(ex)

        if err_msg is not None:
            for email_addr in user_mails:
                for report in reports_to_send:
                    with session_scope() as session:
                        sent_report = session.query(ReportStat).filter(and_(ReportStat.report_id == report.id,
                                                                            ReportStat.email == email_addr)).first()
                        if sent_report is None:

                            session.add(ReportStat(
                                user_id=smtp_settings.user_id,
                                project_id=report.project_id,
                                report_id=report.id,
                                email=email_addr,
                                report_time=checked_time,
                                report_time_unix=unix_time,
                                sent_ok=False,
                                error=err_msg
                            ))
                        else:
                            sent_report.report_time = checked_time
                            sent_report.report_time_unix = unix_time
                            sent_report.sent_ok = False
                            sent_report.error = err_msg
            return

        for report in reports_to_send:
            scan_results_js = get_report_view_data(report.project_id, report.id)
            sschema, saddr, sport = main_module.main_app.get_server_addr()
            report_ref = "%s://%s:%s/report_view/%d/%d" % (sschema, saddr, sport, report.project_id, report.id)
            html_data = jinja_env.get_template("report/email_report_table.html").render(view_data=scan_results_js,
                                                                                        report_ref=report_ref)

            source_address = smtp_settings.mailbox
            email_msg = MIMEMultipart("alternative")
            email_msg["Subject"] = "Report for %s" % report.name
            email_msg["From"] = source_address
            report_table_data = MIMEText(html_data, "html")
            email_msg.attach(report_table_data)

            err_msg = ""
            sent_ok = True
            for email_addr in user_mails:
                log.debug("Trying to send report '%s' to %s" % (report.name, email_addr))
                with session_scope() as session:
                    sent_report = session.query(ReportStat).filter(and_(ReportStat.report_id == report.id,
                                                                        ReportStat.email == email_addr)).first()
                    if sent_report is not None and sent_report.report_time is not None:
                        log.debug("Report time: %s" % sent_report.report_time)
                        if sent_report.sent_ok and compare_time_now(sent_report.report_time, checked_time):
                            log.debug("Report for %s already sent. Skipping..." % email_addr)
                            continue

                    email_msg["To"] = email_addr
                    try:
                        smtp_connection.sendmail(source_address, email_addr, email_msg.as_string())
                    except Exception as ex:
                        tb = traceback.format_exc()
                        log.debug(tb)
                        err_msg = str(ex)
                        sent_ok = False

                    if sent_report is None:
                        session.add(ReportStat(
                            user_id=smtp_settings.user_id,
                            project_id=report.project_id,
                            report_id=report.id,
                            email=email_addr,
                            report_time=checked_time,
                            report_time_unix=unix_time,
                            sent_ok=sent_ok,
                            error=err_msg
                        ))
                    else:
                        sent_report.report_time = checked_time
                        sent_report.report_time_unix = unix_time
                        sent_report.sent_ok = sent_ok
                        sent_report.error = err_msg

        smtp_connection.quit()


def send_report_worker(stop_event, jinja_env):
    signal(SIGINT, SIG_IGN)
    signal(SIGTERM, SIG_IGN)
    while True:
        try:
            while not stop_event.is_set():
                time.sleep(5)
                break
            if stop_event.is_set():
                break
            send_reports(jinja_env)
        except (KeyboardInterrupt, SystemExit):
            log.warning("Exiting report send worker")
            break
        except Exception:
            log.error("Something went wrong while sending reports:\n%s" % str(traceback.format_exc()))
            continue

    log.debug("Reports worker function exited")


class ReportSender:
    def __init__(self, jinja_env):
        self.initialised = False
        self.stop_event = Event()
        self.exited_event = Event()
        self.jinja_env = jinja_env

    def is_initialised(self):
        return self.initialised

    def start(self):
        if not self.is_initialised():
            self.report_process = Process(target=send_report_worker, args=(self.stop_event, self.jinja_env))
            #self.report_process.daemon = True
            self.report_process.start()
            self.initialised = True

    def stop(self):
        log.debug("Setting reports stop event")
        self.stop_event.set()
        log.debug("Reports stop event set")
        if self.report_process:
            log.debug("Trying to join reports worker process")
            self.report_process.join(timeout=5)
            log.debug("Joined successfully")
            

