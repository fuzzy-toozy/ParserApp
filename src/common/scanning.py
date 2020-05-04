import traceback
import os
import errno
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
        self.scan_stats = {}
        self.retries_count = 0
        self.max_retries = 5

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

    def put_scan_object_back(self, product_id, retries):
        try:
            with session_scope(self.username) as session:
                session.add(ScanQueueObject(project_id=self.project_id,
                                            monitoring_id=self.monitoring_id,
                                            monitored_product_id=product_id,
                                            retries=retries))
        except Exception as ex:
            print("put scan object back failed. Project_id: %d, Monitoring_id: %d, Monitored_product_id: %d\nError: %s" %
                  (self.project_id, self.monitoring_id, product_id, str(ex)))

    def init_scan_data(self, scan_stats):
        try:
            with session_scope(self.username) as session:
                monitoring = session.query(Monitoring).filter(and_(Monitoring.id == self.monitoring_id,
                                                                   Project.id == self.project_id)).first()

                scan_stats.scanning_monitoring = monitoring.name
                monitoring_products_and_parsers = session.query(MonitoredProduct, Product, Seller).filter(and_(MonitoredProduct.monitoring_id == self.monitoring_id,
                                                                                                                    MonitoredProduct.project_id == self.project_id,
                                                                                                                    Product.id == MonitoredProduct.product_id,
                                                                                                                    Seller.id == MonitoredProduct.seller_id)).all()

                for scan_data in monitoring_products_and_parsers:
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

    def scan_product(self, stop_event, prod_id):
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
                        return ScanningResult.DOM_FAILED, parser_result
                    elif base_parser:
                        parser_exec_status, parser_result, _, _ = parsing.do_parse(base_parser,
                                                                                   monitored_product.parser_parameter,
                                                                                   page_dom)
                        if not base_scan_res:
                            session.add(BaseScanResult(project_id=monitored_product.project_id,
                                                       monitored_product_id=monitored_product.id,
                                                       monitoring_id=monitored_product.monitoring_id,
                                                       scan_result=parser_result if parser_exec_status == ScanningResult.OK else "",
                                                       scan_error=parser_result,
                                                       result_code=parser_exec_status
                                                       ))
                        else:
                            base_scan_res.scan_result = parser_result
                            base_scan_res.scan_error = parser_result
                            base_scan_res.result_code = parser_exec_status
                    else:
                        if not base_scan_res:
                            session.add(BaseScanResult(project_id=monitored_product.project_id,
                                                       monitored_product_id=monitored_product.id,
                                                       monitoring_id=monitored_product.monitoring_id,
                                                       scan_result="",
                                                       scan_error="No parser found",
                                                       result_code=ScanningResult.NO_PARSER
                                                       ))
                        else:
                            base_scan_res.scan_result = ""
                            base_scan_res.scan_error = "No parser found"
                            base_scan_res.result_code = ScanningResult.NO_PARSER
                except Exception as ex:
                    print(str(ex))
                    traceback.print_exc()
                    return ScanningResult.DATABASE_ERROR, str(ex)

                try:
                    monitored_options_data = session.query(MonitoredOption,
                                                           Parser,
                                                           ProductOption).filter(
                        and_(MonitoredOption.monitored_product_id == monitored_product.id,
                             MonitoredOption.project_id == monitored_product.project_id,
                             ProductOption.id == MonitoredOption.option_id)).outerjoin(Parser,
                                                                                       Parser.id == MonitoredOption.parser_id).all()
                    print("DATA? %s" % monitored_options_data)
                    for monitored_option, option_parser, product_option in monitored_options_data:
                        print("LOL KEK\n")
                        option_parser_exec_status, option_parser_result, _, _ = parsing.do_parse(option_parser,
                                                                                                 monitored_option.parser_parameter,
                                                                                                 page_dom)
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
                                                             scan_result=option_parser_result,
                                                             scan_error=option_parser_result,
                                                             result_code=option_parser_exec_status))
                            else:
                                option_scan_res.scan_result = option_parser_result
                                option_scan_res.scan_error = option_parser_result
                                option_scan_res.result_code = option_parser_exec_status
                        except Exception as ex:
                            print(str(ex))
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
                print("GOT PROD ID: %s" % str(prod_id))
                if not result:
                    last_scan_status = ScanningResult.DATABASE_ERROR
                    last_scan_errmsg = err_msg
                    break
                elif not prod_id:
                    last_scan_status = ScanningResult.FINISHED
                    last_scan_errmsg = ""
                    break
                else:
                    res_code, msg = self.scan_product(stop_event, prod_id)
                    scan_stats.last_object_status = res_code
                    scan_stats.last_object_result = msg
                    if res_code != ScanningResult.OK:
                        if retries < self.max_retries:
                            self.put_scan_object_back(prod_id, retries + 1)
                            continue

                    scan_stats.objects_scanned += 1

                print(msg)
        except Exception as ex:
            last_scan_status = ScanningResult.ERROR
            last_scan_errmsg = str(ex)
            print(last_scan_errmsg)

        try:
            with session_scope(self.username) as session:
                scan_stat = session.query(ScanStat).filter(and_(ScanStat.monitoring_id == self.monitoring_id,
                                                                ScanStat.project_id == self.project_id)).first()

                if scan_stat:
                    scan_stat.last_scan_status = last_scan_status
                    scan_stat.last_scan_ermsg = last_scan_errmsg
                else:
                    session.add(ScanStat(project_id=self.project_id,
                                         monitoring_id=self.monitoring_id,
                                         last_scan_status=last_scan_status,
                                         last_scan_errmsg=last_scan_errmsg))
        except Exception as ex:
            print("Failed adding scan result: %s", str(ex))

        scan_stats.reset()
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
    def __init__(self, queue):
        self.scanning_monitoring = "1"
        self.objects_scanned = 0
        self.reply_queue = queue
        self.last_object_status = ScanningResult.UNKNOWN
        self.last_object_result = ""
        self.qsize = 0

    def worker_stats_sh(self, signum, frame):
        reply_data = {
            "monitoring": self.scanning_monitoring,
            "objects_scanned": self.objects_scanned,
            "qsize": self.qsize,
            "last_obj_stat": self.last_object_status,
            "last_obj_res": self.last_object_result
        }

        self.reply_queue.put(reply_data)

    def reset(self):
        self.scanning_monitoring = ""
        self.objects_scanned = 0
        print("RESETING SCAN STATS")


def do_scan_worker(queue, stats_queue, exit_event):
    scan_stats = ScanStats(stats_queue)
    signal(SIGUSR1, scan_stats.worker_stats_sh)
    while True:
        try:
            monitoring_scanner = queue.get(timeout=3)
            scan_stats.qsize = queue.qsize()
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


class ScanProcessor:
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
            ScanProcessor._send_signal(user_data["process"].pid, SIGUSR1)
            user_queue = user_data["stats_queue"]
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
            user_data["queue"] = user_queue
            user_event = Event()
            user_data["exit_event"] = user_event
            scan_process = Process(target=do_scan_worker, args=(user_queue, stats_queue, user_event))
            user_data["process"] = scan_process
            user_data["stats_queue"] = stats_queue
            scan_process.daemon = True
            scan_process.start()

    def add_scan_object(self, project_id, monitoring_id, user):
        with self.mp_lock:
            user_queue = self.users_data[user]["queue"]
            user_queue.put(MonitoringScanner(project_id, monitoring_id, user))

    def remove_user(self, user):
        with self.mp_lock:
            user_data = self.users_data[user]
            user_process = user_data["process"]
            user_event = user_data["event"]
            user_event.set()
            user_process.join()
            self.users_set.remove(user)
            del self.users_data[user]

    def stop_scan_workers(self):
        with self.mp_lock:
            if not self.users_data:
                return
            for user, user_data in self.users_data.items():
                stop_event = user_data.get("exit_event")
                user_process = user_data.get("process")
                stop_event.set()
                user_process.join()
            self.users_data = None
