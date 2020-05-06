import traceback
import os
import errno

from datetime import datetime
from common import parsing
from database.users import session_scope
from database.models import *
from sqlalchemy import and_
from multiprocessing import Process, Queue, Event, Lock
from queue import Empty
from signal import signal, SIGUSR1


class ScanningResult:
    OK = parsing.ParsingResult.OK

    NO_CODE = parsing.ParsingResult.NO_CODE

    NO_PARSER = parsing.ParsingResult.NO_PARSER

    DOM_FAILED = parsing.ParsingResult.DOM_FAILED

    PARSER_FAILED = parsing.ParsingResult.PARSER_FAILED

    MODULE_FAILED = parsing.ParsingResult.MODULE_FAILED

    FINISHED = MODULE_FAILED + 1

    WARN = FINISHED + 1

    DATABASE_ERROR = WARN + 1

    INTERRUPTED = DATABASE_ERROR + 1

    ERROR = INTERRUPTED + 1

    UNKNOWN = parsing.ParsingResult.UNKNOWN


class MonitoringScanner:

    def __init__(self, project_id, monitoring_id, username):
        self.monitoring_id = monitoring_id
        self.project_id = project_id
        self.username = username
        self.scan_generator = None
        self.retries_count = 0
        self.max_retries = 5

        self.scan_queue = {}
        self.project = None
        self.monitoring = None

        with session_scope(username, True) as session:
            project_and_monitoring = session.query(Monitoring, Project).filter(and_(Monitoring.id == self.monitoring_id,
                                                                               Monitoring.project_id == self.project_id,
                                                                               Project.id == self.project_id)).first()

            if project_and_monitoring:
                self.monitoring = project_and_monitoring[0]
                self.project = project_and_monitoring[1]

        self.request_interval = self.monitoring.request_interval

    def count_retry(self):
        if self.should_retry():
            self.retries_count += 1

    def should_retry(self):
        return self.retries_count < self.max_retries

    def scan_objects_left(self):
        is_ok = False
        result = 0
        try:
            with session_scope(self.username) as session:
                result = session.query(ScanQueueObject).filter(and_(ScanQueueObject.project_id == self.project_id,
                                                                    ScanQueueObject.monitoring_id == self.monitoring_id)).count()
                is_ok = True
        except Exception as ex:
            print("Couldn't get total amount of scan objects for monitoring %d: %s" % (self.monitoring_id, str(ex)))

        return is_ok, result

    def put_scan_object_back(self, product_id, scan_stats, retries):
        try:
            scan_stats.add_retries(product_id)
            with session_scope(self.username) as session:
                session.add(ScanQueueObject(project_id=self.project_id,
                                            monitoring_id=self.monitoring_id,
                                            monitored_product_id=product_id,
                                            retries=retries))
        except Exception as ex:
            print("put scan object back failed. Project_id: %d, Monitoring_id: %d, Monitored_product_id: %d\nError: %s" %
                  (int(self.project_id), int(self.monitoring_id), int(product_id), str(ex)))
            return False
        return True

    def init_scan_data(self, scan_stats):
        try:
            with session_scope(self.username) as session:
                monitoring_products_and_parsers = session.query(MonitoredProduct, Product, Seller).filter(and_(MonitoredProduct.monitoring_id == self.monitoring_id,
                                                                                                                    MonitoredProduct.project_id == self.project_id,
                                                                                                                    Product.id == MonitoredProduct.product_id,
                                                                                                                    Seller.id == MonitoredProduct.seller_id)).all()

                scan_stats.set_state(ScanStats.INIT)
                scan_stats.init(self.project, self.monitoring)
                for scan_data in monitoring_products_and_parsers:
                    scan_object_data = {}
                    scan_object_data["product"] = {"id": scan_data[1].id, "name": scan_data[1].name}
                    scan_object_data["seller"] = {"id": scan_data[2].id, "name": scan_data[2].name}
                    scan_object_data[ScanStats.RETRIES] = 0
                    scan_object_data[ScanStats.BASE] = {}
                    scan_object_data[ScanStats.OPTIONS] = {}
                    scan_stats.add_scan_queue_object(scan_data[0].id, scan_object_data)

                    scan_object = session.query(ScanQueueObject).filter(and_(ScanQueueObject.project_id==scan_data[0].project_id,
                                                                             ScanQueueObject.monitoring_id==scan_data[0].monitoring_id,
                                                                             ScanQueueObject.monitored_product_id==scan_data[0].id)).first()

                    if not scan_object:
                        session.add(ScanQueueObject(project_id=scan_data[0].project_id,
                                                    monitoring_id=scan_data[0].monitoring_id,
                                                    monitored_product_id=scan_data[0].id))
                    else:
                        continue
        except Exception as ex:
            return False, str(ex)

        return True, ""

    def get_next_scan_object(self):
        try:
            retries = 0
            with session_scope(self.username) as session:
                scan_object = session.query(ScanQueueObject).filter(and_(ScanQueueObject.project_id == self.project_id,
                                                                         ScanQueueObject.monitoring_id == self.monitoring_id)).first()

                if scan_object:
                    prod_id = scan_object.monitored_product_id
                    retries = scan_object.retries
                    session.delete(scan_object)
                else:
                    prod_id = None
                return prod_id, True, "", retries
        except Exception as ex:
            traceback.print_exc()
            return None, False, str(ex), -1

    def scan_product(self, stop_event, prod_id, scan_stats):
        scan_stats.set_state(ScanStats.SCAN)
        try:
            with session_scope(self.username) as session:
                monitored_product, base_parser = session.query(MonitoredProduct, Parser).filter(
                    and_(MonitoredProduct.monitoring_id == self.monitoring_id,
                         MonitoredProduct.project_id == self.project_id,
                         MonitoredProduct.id == prod_id)).outerjoin(Parser, Parser.id == MonitoredProduct.parser_id).first()

                try:
                    base_scan_res = session.query(BaseScanResult).filter(and_(BaseScanResult.project_id==monitored_product.project_id,
                                                                              BaseScanResult.monitored_product_id==monitored_product.id,
                                                                              BaseScanResult.monitoring_id==monitored_product.monitoring_id)).first()
                    if not monitored_product:
                        return ScanningResult.WARN, "No monitored product found in database"

                    print("FREAKING MONITORED PRODUCT URL: %s" % monitored_product.url)
                    if stop_event.is_set():
                        return ScanningResult.INTERRUPTED, "Scanning interrupted"
                    page_dom, parser_result = parsing.get_page_dom(monitored_product.url)
                    if page_dom is None:
                        if not base_scan_res:
                            session.add(BaseScanResult(project_id=monitored_product.project_id,
                                                       monitored_product_id=monitored_product.id,
                                                       monitoring_id=monitored_product.monitoring_id,
                                                       scan_result="",
                                                       scan_error=parser_result,
                                                       result_code=ScanningResult.DOM_FAILED
                                                       ))
                        else:
                            base_scan_res.scan_result = ""
                            base_scan_res.scan_error = parser_result
                            base_scan_res.result_code = ScanningResult.DOM_FAILED

                        scan_stats.set_base_scan_data(monitored_product.id, base_parser, ScanningResult.DOM_FAILED, "", parser_result)
                        return ScanningResult.DOM_FAILED, parser_result

                    parser_exec_status, parser_result, _, _ = parsing.do_parse(base_parser,
                                                                               monitored_product.parser_parameter,
                                                                               page_dom)
                    f_parser_result = parser_result if parser_exec_status == ScanningResult.OK else ""
                    f_parser_error = parser_result if not f_parser_result else ""
                    if not base_scan_res:
                        session.add(BaseScanResult(project_id=monitored_product.project_id,
                                                   monitored_product_id=monitored_product.id,
                                                   monitoring_id=monitored_product.monitoring_id,
                                                   scan_result=f_parser_result,
                                                   scan_error=f_parser_error,
                                                   result_code=parser_exec_status
                                                   ))
                    else:
                        base_scan_res.scan_result = f_parser_result
                        base_scan_res.scan_error = f_parser_error
                        base_scan_res.result_code = parser_exec_status

                    scan_stats.set_base_scan_data(monitored_product.id, base_parser, parser_exec_status,
                                                  f_parser_result, f_parser_error)


                except Exception as ex:
                    err_msg = str(ex)
                    scan_stats.set_base_scan_data(monitored_product.id, base_parser, ScanningResult.DATABASE_ERROR, "", err_msg)
                    traceback.print_exc()
                    return ScanningResult.DATABASE_ERROR, err_msg

                try:
                    monitored_options_data = session.query(MonitoredOption,
                                                           Parser,
                                                           ProductOption).filter(
                        and_(MonitoredOption.monitored_product_id == monitored_product.id,
                             MonitoredOption.project_id == monitored_product.project_id,
                             ProductOption.id == MonitoredOption.option_id)).outerjoin(Parser,
                                                                                       Parser.id == MonitoredOption.parser_id).all()

                    for monitored_option, option_parser, product_option in monitored_options_data:
                        option_parser_exec_status, option_parser_result, _, _ = parsing.do_parse(option_parser,
                                                                                                 monitored_option.parser_parameter,
                                                                                                 page_dom)
                        f_option_parser_result = option_parser_result if option_parser_exec_status == ScanningResult.OK else ""
                        f_option_parser_error = option_parser_result if not f_option_parser_result else ""

                        try:
                            option_scan_res = session.query(OptionScanResult).filter(
                                and_(OptionScanResult.project_id == monitored_option.project_id,
                                     OptionScanResult.monitored_product_id == monitored_option.monitored_product_id,
                                     OptionScanResult.monitoring_id == monitored_option.monitoring_id,
                                     OptionScanResult.option_id == monitored_option.id)).first()

                            if not option_scan_res:
                                session.add(OptionScanResult(project_id=monitored_option.project_id,
                                                             option_id=monitored_option.id,
                                                             monitoring_id=monitored_option.monitoring_id,
                                                             monitored_product_id=monitored_option.monitored_product_id,
                                                             scan_result=f_option_parser_result,
                                                             scan_error=f_option_parser_error,
                                                             result_code=option_parser_exec_status))
                            else:
                                option_scan_res.scan_result = f_option_parser_result
                                option_scan_res.scan_error = f_option_parser_error
                                option_scan_res.result_code = option_parser_exec_status

                            scan_stats.set_option_scan_data(monitored_product.id, product_option.name, option_parser, option_parser_exec_status, f_option_parser_result, f_option_parser_error)
                        except Exception as ex:
                            err_msg = str(ex)
                            scan_stats.set_option_scan_data(monitored_product.id, product_option.name, option_parser,
                                                      ScanningResult.DATABASE_ERROR, "", err_msg)
                            traceback.print_exc()
                            continue
                except Exception as ex:
                    print(str(ex))
                    traceback.print_exc()
                    return ScanningResult.DATABASE_ERROR, str(ex)
        except Exception as ex:
            print("WOOOOPS\n")
            print(str(ex))
            traceback.print_exc()
            return ScanningResult.DATABASE_ERROR, str(ex)

        return ScanningResult.OK, "Scan is ok"

    def run_scan(self, stop_event, scan_stats):
        last_scan_status = ScanningResult.OK
        last_scan_errmsg = ""

        try:
            while not stop_event.is_set():
                prod_id, result, err_msg, retries = self.get_next_scan_object()
                print("product id: %s, result: %s, err: %s, retrs: %d" % (str(prod_id), result, err_msg, retries))
                if not result:
                    last_scan_status = ScanningResult.DATABASE_ERROR
                    last_scan_errmsg = err_msg
                    break
                elif not prod_id:
                    last_scan_status = ScanningResult.FINISHED
                    last_scan_errmsg = ""
                    break
                else:
                    res_code, msg = self.scan_product(stop_event, prod_id, scan_stats)
                    scan_stats.last_object_status = res_code
                    scan_stats.last_object_result = msg
                    if res_code != ScanningResult.OK:
                        if retries < self.max_retries:
                            pushed_back = self.put_scan_object_back(prod_id, scan_stats, retries + 1)
                            if not pushed_back: scan_stats.finalize_object(prod_id)
                            stop_event.wait(self.request_interval)
                            continue
                    stop_event.wait(self.request_interval)
                    scan_stats.finalize_object(prod_id)
        except Exception as ex:
            last_scan_status = ScanningResult.ERROR
            last_scan_errmsg = str(ex)
            print(last_scan_errmsg)

        return last_scan_status, last_scan_errmsg

    def get_json_results(self):
        results = []
        with session_scope(self.username) as session:
            scan_res = session.query(BaseScanResult).filter(and_(BaseScanResult.monitoring_id == self.monitoring_id,
                                                                 BaseScanResult.project_id == self.project_id)).all()

            for x in scan_res:
                base_res = {}
                base_res["base"] = {"code": x.result_code, "result": x.scan_result, "error": x.scan_error}
                options = []
                options_res = session.query(OptionScanResult).filter(and_(OptionScanResult.monitoring_id == self.monitoring_id,
                                                                          OptionScanResult.project_id == self.project_id,
                                                                          OptionScanResult.monitored_product_id == x.monitored_product_id)).all()

                for option in options_res:
                    options.append({"code": option.result_code, "result": option.scan_result, "error": option.scan_error})
                base_res["options"] = options
                results.append(base_res)

        return results


class ScanStats:
    INIT = 0x1488
    SCAN = 0x1489
    IDLE = 0x1490

    STATES = {INIT: "Initialising", SCAN: "Scanning", IDLE: "Idle"}

    RESCODE = "rescode"
    ERROR = "error"
    RESULT = "result"
    OPTIONS = "options"
    RETRIES = "retries"
    BASE = "base"
    STATE = "state"
    LAST_SCAN = "last_scan_data"
    PROJECT = "project"
    MONITORING = "monitoring"
    QUEUED = "queued"
    PROCESSED = "processed"
    SCANNED = "objects_scanned"
    SCANNED_QUEUE = "scanned_queue"
    SCAN_STARTED = "scan_started"
    SCAN_FINISHED = "scan_finished"
    PARSER = "parser"

    def __init__(self, queue):
        self.current_monitoring = None
        self.current_project = None
        self.scan_queue = {}
        self.scanned_queue = {}
        self.last_scanned_data = {}

        self.current_state = ScanStats.IDLE

        self.reply_queue = queue

        self.objects_scanned = 0
        self.qsize = 0
        self.start_time = 0

    def init(self, project, monitoring):
        self.current_monitoring = monitoring
        self.current_project = project
        self.start_time = datetime.now()

    def set_base_scan_data(self, product_id, parser, rescode, result, errmsg):
        base_data = self.scan_queue[product_id][ScanStats.BASE]
        base_data[ScanStats.RESCODE] = rescode
        base_data[ScanStats.ERROR] = errmsg
        base_data[ScanStats.RESULT] = result
        base_data[ScanStats.PARSER] =  {"id": parser.id, "name": parser.name} if parser else {}

    def set_option_scan_data(self, product_id, option_name, parser, rescode, result, errmsg):
        option_data = {
            ScanStats.RESCODE: rescode,
            ScanStats.RESULT: result,
            ScanStats.ERROR: errmsg,
            ScanStats.PARSER: {"id": parser.id, "name": parser.name} if parser else {}
        }
        self.scan_queue[product_id][ScanStats.OPTIONS][option_name] = option_data

    def add_retries(self, product_id):
        self.scan_queue[product_id][ScanStats.RETRIES] += 1

    def add_scan_queue_object(self, product_id, object_data):
        self.scan_queue[product_id] = object_data

    def set_state(self, state):
        self.current_state = state

    def finalize_object(self, product_id):
        product_data = self.scan_queue[product_id]
        del self.scan_queue[product_id]
        self.scanned_queue[product_id] = product_data
        self.objects_scanned += 1

    def worker_stats_sh(self, signum, frame):
        reply_data = {ScanStats.STATE: self.STATES[self.current_state],
                      ScanStats.PROJECT: "",
                      ScanStats.MONITORING: "",
                      ScanStats.QUEUED: {},
                      ScanStats.PROCESSED: {},
                      ScanStats.SCANNED: 0}

        if self.current_state == ScanStats.IDLE:
            reply_data[ScanStats.LAST_SCAN] = self.last_scanned_data
        else:
            reply_data[ScanStats.PROJECT] = self.current_project.name
            reply_data[ScanStats.MONITORING] = self.current_monitoring.name

            if self.current_state == ScanStats.SCAN:
                reply_data[ScanStats.SCAN_STARTED] = self.start_time
                reply_data[ScanStats.QUEUED] = self.scan_queue
                reply_data[ScanStats.PROCESSED] = self.scanned_queue
                reply_data[ScanStats.SCANNED] = self.objects_scanned

        self.reply_queue.put(reply_data)

    def reset(self):
        if self.current_monitoring:
            self.last_scanned_data[ScanStats.MONITORING] = self.current_monitoring.name
            self.last_scanned_data[ScanStats.PROJECT] = self.current_project.name
            self.last_scanned_data[ScanStats.SCANNED_QUEUE] = self.scanned_queue
            self.last_scanned_data[ScanStats.SCAN_STARTED] = self.start_time
            self.last_scanned_data[ScanStats.SCAN_FINISHED] = datetime.now()
            self.last_scanned_data[ScanStats.SCANNED] = self.objects_scanned

        self.current_state = ScanStats.IDLE
        self.scan_queue = {}
        self.scanned_queue = {}
        self.current_monitoring = None
        self.current_project = None
        self.objects_scanned  = 0
        self.start_time = 0


def do_scan_worker(queue, stats_queue, exit_event):
    scan_stats = ScanStats(stats_queue)
    signal(SIGUSR1, scan_stats.worker_stats_sh)
    while True:
        try:
            monitoring_scanner = queue.get(timeout=3)
            scan_stats.qsize = queue.qsize()
            print(monitoring_scanner)
            init_res, err_msg = monitoring_scanner.init_scan_data(scan_stats)
            if init_res:
                scan_res, _ = monitoring_scanner.run_scan(exit_event, scan_stats)
            else:
                print("Failed to initialise scan data: %s" % err_msg)
        except (KeyboardInterrupt, SystemExit):
            print("Exiting user thread")
            break
        except Empty:
            if exit_event.is_set():
                break
            continue
        except Exception as ex:
            print("Something went wrong while gay scan: %s" % str(ex))
            continue
        finally:
            scan_stats.reset()


class ScanProcessor:

    PROCESS = "process"
    STATS_QUEUE = "stats_queue"
    QUEUE = "queue"
    EVENT = "event"
    EXIT_EVENT = "exit_event"

    def __init__(self):
        print("BLEAT")
        self.users_set = None
        self.users_data = {}
        self.initialised = False
        self.mp_lock = Lock()

    @staticmethod
    def _send_signal(pid, signum):
        if pid:
            try:
                os.kill(pid, signum)
            except OSError:
                if OSError.errno == errno.ESRCH:
                    return
                else:
                    raise

    def init_users(self, users_set):
        with self.mp_lock:
            if not self.users_set:
                self.users_set = users_set
                self.initialised = True

    def is_initialised(self):
        return self.initialised

    def get_stats(self, user):
        with self.mp_lock:
            user_data = self.users_data[user]
            ScanProcessor._send_signal(user_data[ScanProcessor.PROCESS].pid, SIGUSR1)
            user_queue = user_data[ScanProcessor.STATS_QUEUE]
            result = {}
            try:
                result = user_queue.get(timeout=3)
            except Empty:
                pass
        return result

    def run_scan(self):
        for user in self.users_set:
            user_data = {}
            self.users_data[user] = user_data
            user_queue = Queue()
            stats_queue = Queue()
            user_data[ScanProcessor.QUEUE] = user_queue
            user_event = Event()
            user_data[ScanProcessor.EXIT_EVENT] = user_event
            scan_process = Process(target=do_scan_worker, args=(user_queue, stats_queue, user_event))
            user_data[ScanProcessor.PROCESS] = scan_process
            user_data[ScanProcessor.STATS_QUEUE] = stats_queue
            scan_process.daemon = True
            scan_process.start()

    def add_scan_object(self, project_id, monitoring_id, user):
        with self.mp_lock:
            user_queue = self.users_data[user][ScanProcessor.QUEUE]
            user_queue.put(MonitoringScanner(project_id, monitoring_id, user))

    def remove_user(self, user):
        with self.mp_lock:
            user_data = self.users_data[user]
            user_process = user_data[ScanProcessor.PROCESS]
            user_event = user_data[ScanProcessor.EVENT]
            user_event.set()
            user_process.join()
            self.users_set.remove(user)
            del self.users_data[user]

    def stop_scan_workers(self):
        with self.mp_lock:
            if not self.users_data:
                return
            for user, user_data in self.users_data.items():
                stop_event = user_data.get(ScanProcessor.EXIT_EVENT)
                user_process = user_data.get(ScanProcessor.PROCESS)
                stop_event.set()
                user_process.join()
            self.users_data = None
