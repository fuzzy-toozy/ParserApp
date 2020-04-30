import traceback

from common import parsing
from database.users import session_scope
from database.models import *
from sqlalchemy import and_


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

    UNKNOWN = parsing.ParsingResult.UNKNOWN


class MonitoringScanner:

    def __init__(self, project_id, monitoring_id, username):
        self.monitoring_id = monitoring_id
        self.project_id = project_id
        self.username = username
        self.scan_generator = None

    def init_scan_data(self):
        try:
            with session_scope(self.username) as session:
                monitoring_products_and_parsers = session.query(MonitoredProduct, Product, Seller).filter(and_(MonitoredProduct.monitoring_id == self.monitoring_id,
                                                                                                                    MonitoredProduct.project_id == self.project_id,
                                                                                                                    Product.id == MonitoredProduct.product_id,
                                                                                                                    Seller.id == MonitoredProduct.seller_id)).all()
                print("WHY: %s" % str(monitoring_products_and_parsers))
                for scan_data in monitoring_products_and_parsers:
                    session.add(ScanQueueObject(project_id=scan_data[0].project_id,
                                                monitoring_id=scan_data[0].monitoring_id,
                                                monitored_product_id=scan_data[0].id))
                    print("lil\n")
        except Exception as ex:
            return False, str(ex)

        return True, ""

    def get_next_scan_object(self):
        try:
            with session_scope(self.username) as session:
                scan_object = session.query(ScanQueueObject).filter(and_(ScanQueueObject.project_id == self.project_id,
                                                                         ScanQueueObject.monitoring_id == self.monitoring_id)).first()

                if scan_object:
                    prod_id = scan_object.monitored_product_id
                    session.delete(scan_object)
                else:
                    prod_id = None
                return prod_id, True, ""
        except Exception as ex:
            traceback.print_exc()
            return None, False, str(ex)

    def scan_product(self):
        prod_id, result, err_msg = self.get_next_scan_object()
        print("GOT PROD ID: %s" % str(prod_id))
        if not result:
            return ScanningResult.DATABASE_ERROR, err_msg
        elif not prod_id:
            return ScanningResult.FINISHED, ""

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
                                                       scan_result=parser_result,
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

        return ScanningResult.OK, ""

    def get_json_results(self):
        results = []
        print("AAHAHAHH")
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
