import flask
import json

from flask_login import login_required, current_user
from flask import Blueprint

from sqlalchemy import and_, desc

from database.models import *
from database.users import session_scope
from routes.shared import bc_generator, ENTS

reports = Blueprint("reports", __name__)


@reports.route("/reports_view/<project_id>", methods=['GET'])
@login_required
def reports_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.REPORTS)
    with session_scope(current_user.username, True) as session:
        current_reports = session.query(ScanReport).filter(ScanReport.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('reports.create_report', project_id=project_id)
    delete_entity_url = flask.url_for('reports.delete_report')
    entity_view_url = flask.url_for('reports.reports_view', project_id=project_id)
    view_entity = 'reports.report_view'
    edit_entity = 'reports.edit_report'

    return flask.render_template("report/reports_view.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 entities=current_reports,
                                 common_name="report",
                                 new_entity_url=new_entity_url,
                                 delete_entity_url =delete_entity_url,
                                 entity_view_url=entity_view_url,
                                 edit_entity=edit_entity,
                                 view_entity=view_entity,
                                 bc_data=bc_data,
                                 create_ent_txt="Create report")


@reports.route("/delete_report", methods=['POST'])
@login_required
def delete_report():
    request_js = flask.request.get_json()
    report_id = request_js['id']
    project_id = request_js['project_id']
    with session_scope(current_user.username) as session:
        session.query(ScanReport).filter(ScanReport.id == report_id).delete()
    return flask.redirect(flask.url_for("reports.reports_view", project_id=project_id))


@reports.route("/report_view/<project_id>/<entity_id>", methods=['GET'])
@login_required
def report_view(project_id, entity_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, None, [ENTS.REPORTS],
                                                ScanReport, entity_id, ENTS.REPORT)
    with session_scope(current_user.username) as session:
        report_objects = session.query(ScanReportObject).filter(ScanReportObject.report_id == entity_id,
                                                                ScanReportObject.project_id == project_id).all()

        report_monitored_products = [report_object.monitored_product_id for report_object in report_objects]
        scan_results = session.query(BaseScanResult, MonitoredProduct, Product, Seller).filter(
            and_(BaseScanResult.project_id == project_id,
                 BaseScanResult.monitored_product_id.in_(report_monitored_products),
                 MonitoredProduct.project_id == project_id,
                 MonitoredProduct.id == BaseScanResult.monitored_product_id,
                 Product.id == MonitoredProduct.product_id,
                 Seller.id == MonitoredProduct.seller_id)).all()

        scan_results_js = {}
        for result, mon_product, product, seller in scan_results:
            current_result = scan_results_js.get(product.name)
            if current_result is None:
                current_result = {}
                product_options = session.query(ProductOption).filter(ProductOption.product_id == product.id).all()
                options_struct = {x.name: "" for x in product_options}
                current_result["all_opts"] = options_struct
                sellers_data = {}
                current_result["sellers"] = sellers_data
                scan_results_js[product.name] = current_result

            sellers_data = current_result["sellers"]
            current_seller_result = sellers_data.get(seller.name)

            if current_seller_result is None:
                current_seller_result = {}
                sellers_data[seller.name] = current_seller_result

            current_seller_result["rescode"] = result.result_code
            current_seller_result["result"] = result.scan_result
            current_seller_result["error"] = result.scan_error
            options_result = {}
            current_seller_result["options"] = options_result

            scan_options_results = session.query(OptionScanResult, MonitoredOption, ProductOption).filter(
                and_(OptionScanResult.project_id == project_id,
                     MonitoredOption.monitored_product_id == mon_product.id,
                     MonitoredOption.id == OptionScanResult.option_id,
                     MonitoredOption.project_id == project_id)).outerjoin(ProductOption,
                                                                          ProductOption.id == MonitoredOption.option_id).all()


            print("SCAN OPTIONS RESULT %s" % scan_options_results)

            for option_result, mon_option, product_option in scan_options_results:
                current_option = {}
                current_option["rescode"] = option_result.result_code
                current_option["result"] = option_result.scan_result
                current_option["error"] = option_result.scan_error
                options_result[product_option.name] = current_option

        print("FINAL SHIT\n%s" % scan_results_js)

        return flask.render_template("report/report_view.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 bc_data=bc_data,
                                 view_data=scan_results_js)


DAYS_OF_WEEK = (
    ("Monday", 1),
    ("Tuesday", 2),
    ("Wednesday", 3),
    ("Thursday", 4),
    ("Friday", 5),
    ("Saturday", 6),
    ("Sunday", 7)
)

ID_TO_DAY = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday"
}


def get_monitored_products_and_sellers(username, project_id, monitoring_id):
    with session_scope(username, True) as session:
        monitored_entities_res = session.query(MonitoredProduct, Product, Seller).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                                                              MonitoredProduct.project_id == project_id,
                                                                                              MonitoringProduct.id == MonitoredProduct.monitoring_product_id,
                                                                                              MonitoringSeller.id == MonitoredProduct.monitoring_seller_id,
                                                                                              Product.id == MonitoringProduct.product_id,
                                                                                              Seller.id == MonitoringSeller.seller_id)).order_by(desc(Seller.id)).all()
        seller_to_product = {}

        for monitored_object, product, seller in monitored_entities_res:
            current_data = seller_to_product.get(seller.name)

            if not current_data:
                current_data = []
                object_data = {"seller_id": seller.id, "products": current_data}
                seller_to_product[seller.name] = object_data
            else:
                current_data = current_data["products"]

            current_data.append((monitored_object.id, product))

        seller_to_product = sorted(seller_to_product.items())
        print(seller_to_product)

        return seller_to_product


@reports.route("/get_monitoring_objects/<project_id>/<monitoring_id>", methods=['POST'])
@login_required
def get_monitoring_objects(project_id, monitoring_id):
    seller_to_products = get_monitored_products_and_sellers(current_user.username, project_id, monitoring_id)
    if seller_to_products:
        return flask.render_template("report/monitoring_objects.html", seller_to_products=seller_to_products)
    else:
        return "No monitoring objects created"


@reports.route("/create_report/<project_id>/new_entity", methods=['GET'])
@login_required
def create_report(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.EDIT_REPORT, [ENTS.REPORTS])
    with session_scope(current_user.username, True) as session:
        current_products = session.query(Product).filter(Product.project_id == int(project_id)).all()
        current_sellers = session.query(Seller).filter(Seller.project_id == int(project_id)).all()
        project_monitorings = session.query(Monitoring).filter(Monitoring.project_id == int(project_id)).all()
        seltop = get_monitored_products_and_sellers(current_user.username, project_id, 5)

    return flask.render_template("report/edit_report.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 entity_id="new_entity",
                                 project_monitorings=project_monitorings,
                                 seller_to_products={},
                                 bc_data=bc_data,
                                 save_url=flask.url_for("reports.save_report"),
                                 days_of_week=DAYS_OF_WEEK,
                                 redirect_url=flask.url_for("reports.reports_view", project_id=project_id))


@reports.route("/edit_report/<project_id>/<entity_id>", methods=['GET'])
@login_required
def edit_report(project_id, entity_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.EDIT_REPORT, [ENTS.REPORTS])
    with session_scope(current_user.username, True) as session:
        current_products = session.query(Product).filter(Product.project_id == int(project_id)).all()
        current_sellers = session.query(Seller).filter(Seller.project_id == int(project_id)).all()
        project_monitorings = session.query(Monitoring).filter(Monitoring.project_id == int(project_id)).all()
        seltop = get_monitored_products_and_sellers(current_user.username, project_id, 5)

        scan_report = session.query(ScanReport).filter(and_(ScanReport.project_id == project_id,
                                                            ScanReport.id == entity_id)).first()

        scan_objects = session.query(ScanReportObject).filter(and_(ScanReportObject.project_id == project_id,
                                                                   ScanReportObject.report_id == scan_report.id)).all()

        selected_object_ids = {scan_object.monitored_product_id: 0 for scan_object in scan_objects}

        view_data = {"monitoring": scan_report.monitoring_id,
                     "objects": selected_object_ids,
                     "timestamp": scan_report.report_time,
                     "notify": scan_report.notifications_enabled,
                     "days": scan_report.days_of_week,
                     "name": scan_report.name}
        view_data = view_data


    return flask.render_template("report/edit_report.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 entity_id=scan_report.id,
                                 view_data=view_data,
                                 selected_objects=selected_object_ids,
                                 project_monitorings=project_monitorings,
                                 seller_to_products=seltop,
                                 bc_data=bc_data,
                                 save_url=flask.url_for("reports.save_report"),
                                 days_of_week=DAYS_OF_WEEK,
                                 redirect_url=flask.url_for("reports.reports_view", project_id=project_id))


@reports.route("/save_report", methods=['POST'])
@login_required
def save_report():
    request_json = flask.request.get_json()
    monitored_objects = request_json["monitoring_objects"];
    report_name = request_json["name"];
    report_days = request_json["days"];
    report_enabled = request_json["email_enabled"];
    report_timestamp = request_json["utc_epoch"];
    project_id = request_json["project_id"];
    report_id = request_json["entity_id"];
    monitoring_id = request_json["monitoring_id"];
    days_of_week = json.dumps(report_days)

    print(request_json)

    with session_scope(current_user.username) as session:
        if report_id == "new_entity":
            current_report = ScanReport(project_id=project_id,
                                        monitoring_id=monitoring_id,
                                        notifications_enabled=report_enabled,
                                        report_time=report_timestamp,
                                        days_of_week=days_of_week,
                                        name=report_name)

            session.add(current_report)
            session.flush()

            objects_to_insert = set()
            for seller_id, seller_products in monitored_objects.items():
                for monitored_object_id in seller_products:
                    objects_to_insert.add(monitored_object_id)

        else:
            current_report = session.query(ScanReport).filter(and_(ScanReport.id == report_id,
                                                                   ScanReport.project_id == project_id)).first()

            current_report.report_time = report_timestamp
            current_report.name = report_name
            current_report.days_of_week = days_of_week
            current_report.notifications_enabled = report_enabled
            current_report.monitoring_id = monitoring_id

            objects_result = session.query(ScanReportObject).filter(and_(ScanReportObject.report_id == ScanReport.id,
                                                                         ScanReportObject.project_id == project_id)).all()

            db_monitored_objects = {scan_object.monitored_product_id for scan_object in objects_result}
            request_monitored_objects = set()
            for seller_id, seller_products in monitored_objects.items():
                for monitored_object_id in seller_products:
                    request_monitored_objects.add(monitored_object_id)

            objects_to_delete = db_monitored_objects - request_monitored_objects
            objects_to_insert = request_monitored_objects - db_monitored_objects

            for object_id in objects_to_delete:
                session.query(ScanReportObject).filter(and_(ScanReportObject.project_id == project_id,
                                                            ScanReportObject.report_id == current_report.id,
                                                            ScanReportObject.monitored_product_id == object_id)).delete()

        for object_id in objects_to_insert:
            new_report_object = ScanReportObject(project_id=project_id,
                                                 report_id=current_report.id,
                                                 monitored_product_id=object_id)

            session.add(new_report_object)

    return "OK"
