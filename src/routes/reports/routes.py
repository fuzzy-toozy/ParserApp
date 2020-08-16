import flask
import json
from datetime import datetime

from flask_login import login_required, current_user
from flask import Blueprint

from sqlalchemy import and_, desc, asc

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
        scan_report = session.query(ScanReport).filter(and_(ScanReport.id == entity_id,
                                                            ScanReport.project_id == project_id)).first()

        monitoring_data = session.query(ScanReportProduct, ScanReportSeller, Product, Seller).filter(and_(ScanReportProduct.report_id == entity_id,
                                                                                                          ScanReportSeller.report_id == entity_id,
                                                                                                          ScanReportProduct.project_id == project_id,
                                                                                                          ScanReportSeller.project_id == project_id,
                                                                                                          MonitoringProduct.monitoring_id == scan_report.monitoring_id,
                                                                                                          MonitoringProduct.id == ScanReportProduct.monitoring_product_id,
                                                                                                          MonitoringSeller.id == ScanReportSeller.monitoring_seller_id,
                                                                                                          Product.id == MonitoringProduct.product_id,
                                                                                                          Seller.id == MonitoringSeller.seller_id)).all()

        print(monitoring_data)

        monitored_products = session.query(MonitoredProduct).filter(and_(MonitoredProduct.project_id == project_id,
                                                                         MonitoredProduct.monitoring_id == scan_report.monitoring_id,
                                                                         ScanReportProduct.monitoring_product_id == MonitoredProduct.monitoring_product_id,
                                                                         ScanReportSeller.monitoring_seller_id == MonitoredProduct.monitoring_seller_id)).all()

        mon_prod_check = {}
        mon_prod_exists = {}

        for mon_prod in monitored_products:
            mon_sel = mon_prod_exists.get(mon_prod.product_id)
            if mon_sel is None:
                mon_sel = {}
                mon_prod_exists[mon_prod.product_id] = mon_sel
            mon_sel[mon_prod.seller_id] = True

        report_monitored_products = [x.id for x in monitored_products]

        scan_results = session.query(BaseScanResult, MonitoredProduct, Product, Seller).filter(
            and_(BaseScanResult.project_id == project_id,
                 BaseScanResult.monitored_product_id.in_(report_monitored_products),
                 MonitoredProduct.project_id == project_id,
                 MonitoredProduct.id == BaseScanResult.monitored_product_id,
                 Product.id == MonitoredProduct.product_id,
                 Seller.id == MonitoredProduct.seller_id)).all()

        print("Scan results: %s" % scan_results)
        scan_results_js = {}
        for result, mon_product, product, seller in scan_results:
            mon_prod_data = mon_prod_check.get(mon_product.product_id)
            if mon_prod_data is None:
                mon_prod_data = {}
                mon_prod_check[mon_product.product_id] = mon_prod_data
            mon_prod_data[mon_product.seller_id] = True
            current_result = scan_results_js.get(product.name)
            if current_result is None:
                current_result = {}
                product_options = session.query(ProductOption).filter(ProductOption.product_id == product.id).order_by(ProductOption.id.asc()).all()
                options_struct = [x.name for x in product_options]
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
            current_seller_result["time"] = datetime.utcfromtimestamp(result.last_scan_time).strftime('%X %Zon %b %d, %Y') + " UTC"
            current_seller_result["url"] = mon_product.url if mon_product.url else ""
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
                current_option["time"] = datetime.utcfromtimestamp(option_result.last_scan_time).strftime('%X %Zon %b %d, %Y') + " UTC"
                options_result[product_option.name] = current_option

        for s_product, s_seller, product, seller in monitoring_data:
            print("pname: %s sname: %s" % (product.name, seller.name))
            product_exists = mon_prod_check.get(product.id)
            if product_exists:
                seller_exists = product_exists.get(seller.id)
                if product_exists and seller_exists:
                    continue

            product_exists = mon_prod_exists.get(product.id)
            seller_exists = False
            if product_exists:
                seller_exists = product_exists.get(seller.id)

            seller_data = dict()

            seller_data["rescode"] = -50 if seller_exists else -100
            seller_data["result"] = ""
            seller_data["error"] = ""
            seller_data["time"] = ""
            seller_data["url"] = ""
            seller_data["options"] = {}

            seller_object = dict()
            seller_object[seller.name] = seller_data

            product_to_update = scan_results_js.get(product.name)

            if product_to_update is not None:
                sellers_to_update = product_to_update.get("sellers")
                if sellers_to_update is None:
                    sellers_main_object = {}
                    sellers_main_object.update(seller_object)
                    product_to_update["sellers"] = sellers_main_object
                else:
                    sellers_to_update.update(seller_object)
            else:
                product_data = dict()
                sellers_data = dict()
                product_data["sellers"] = sellers_data
                sellers_data.update(seller_object)
                product_options = session.query(ProductOption).filter(
                    ProductOption.product_id == product.id).order_by(ProductOption.id.asc()).all()
                options_struct = [x.name for x in product_options]
                product_data["all_opts"] = options_struct

                scan_results_js[product.name] = product_data


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
    with session_scope(current_user.username) as session:
        monitoring_sellers = session.query(MonitoringSeller, Seller).filter(and_(MonitoringSeller.monitoring_id == monitoring_id,
                                                                                 MonitoringSeller.project_id == project_id,
                                                                                 Seller.id == MonitoringSeller.seller_id)).order_by(desc(Seller.id)).all()

        monitoring_products = session.query(MonitoringProduct, Product).filter(and_(MonitoringProduct.monitoring_id == monitoring_id,
                                                                                    MonitoringProduct.project_id == project_id,
                                                                                    Product.id == MonitoringProduct.product_id)).order_by(desc(Product.id)).all()
        sellers_data = []
        products_data = []
        for m_seller, seller in monitoring_sellers:
            sellers_data.append((m_seller.id, seller.name))

        for m_product, product in monitoring_products:
            products_data.append((m_product.id, product.name))

        return flask.render_template("report/monitoring_objects.html",
                                     sellers_data=sellers_data,
                                     products_data=products_data)


@reports.route("/create_report/<project_id>/new_entity", methods=['GET'])
@login_required
def create_report(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.EDIT_REPORT, [ENTS.REPORTS])
    with session_scope(current_user.username, True) as session:
        project_monitorings = session.query(Monitoring).filter(Monitoring.project_id == int(project_id)).all()

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
        project_monitorings = session.query(Monitoring).filter(Monitoring.project_id == int(project_id)).all()
        seltop = get_monitored_products_and_sellers(current_user.username, project_id, 5)

        scan_report = session.query(ScanReport).filter(and_(ScanReport.project_id == project_id,
                                                            ScanReport.id == entity_id)).first()

        scan_sellers = session.query(ScanReportSeller).filter(and_(ScanReportSeller.project_id == project_id,
                                                                   ScanReportSeller.report_id == scan_report.id)).all()

        scan_products = session.query(ScanReportProduct).filter(and_(ScanReportProduct.project_id == project_id,
                                                                     ScanReportProduct.report_id == scan_report.id)).all()

        selected_sellers_ids = {scan_object.monitoring_seller_id: 0 for scan_object in scan_sellers}
        selected_products_ids = {scan_object.monitoring_product_id: 0 for scan_object in scan_products}

        view_data = {"monitoring": scan_report.monitoring_id,
                     "sellers": selected_sellers_ids,
                     "products": selected_products_ids,
                     "timestamp": scan_report.report_time,
                     "notify": scan_report.notifications_enabled,
                     "days": scan_report.days_of_week,
                     "name": scan_report.name}

    return flask.render_template("report/edit_report.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 entity_id=scan_report.id,
                                 view_data=view_data,
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

    sellers_objects_to_insert = set()
    for monitoring_seller_id in monitored_objects["sellers"]:
        sellers_objects_to_insert.add(monitoring_seller_id)

    products_objects_to_insert = set()
    for monitoring_product_id in monitored_objects["products"]:
        products_objects_to_insert.add(monitoring_product_id)

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
        else:
            current_report = session.query(ScanReport).filter(and_(ScanReport.id == report_id,
                                                                   ScanReport.project_id == project_id)).first()

            current_report.report_time = report_timestamp
            current_report.name = report_name
            current_report.days_of_week = days_of_week
            current_report.notifications_enabled = report_enabled
            current_report.monitoring_id = monitoring_id

            monitoring_sellers_db = session.query(ScanReportSeller).filter(and_(ScanReportSeller.report_id == ScanReport.id,
                                                                                ScanReportSeller.project_id == project_id)).all()

            monitoring_products_db = session.query(ScanReportProduct).filter(and_(ScanReportProduct.report_id == ScanReport.id,
                                                                                  ScanReportProduct.project_id == project_id)).all()

            db_monitored_sellers = {scan_object.monitoring_seller_id for scan_object in monitoring_sellers_db}
            db_monitored_products = {scan_object.monitoring_product_id for scan_object in monitoring_products_db}

            sellers_to_delete = db_monitored_sellers - sellers_objects_to_insert
            sellers_objects_to_insert = sellers_objects_to_insert - db_monitored_sellers
            products_to_delete = db_monitored_products - products_objects_to_insert
            products_objects_to_insert = products_objects_to_insert - db_monitored_products

            for object_id in sellers_to_delete:
                session.query(ScanReportSeller).filter(and_(ScanReportSeller.project_id == project_id,
                                                            ScanReportSeller.report_id == current_report.id,
                                                            ScanReportSeller.monitoring_seller_id == object_id)).delete()
            for object_id in products_to_delete:
                session.query(ScanReportProduct).filter(and_(ScanReportProduct.project_id == project_id,
                                                             ScanReportProduct.report_id == current_report.id,
                                                             ScanReportProduct.monitoring_product_id == object_id)).delete()

        for object_id in sellers_objects_to_insert:
            new_report_object = ScanReportSeller(project_id=project_id,
                                                 report_id=current_report.id,
                                                 monitoring_seller_id=object_id)
            session.add(new_report_object)

        for object_id in products_objects_to_insert:
            new_report_object = ScanReportProduct(project_id=project_id,
                                                  report_id=current_report.id,
                                                  monitoring_product_id=object_id)
            session.add(new_report_object)

    return "OK"
