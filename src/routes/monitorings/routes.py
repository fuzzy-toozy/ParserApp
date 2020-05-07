import flask

from collections import OrderedDict

from flask_login import login_required, current_user
from flask import Blueprint

from sqlalchemy import and_

from database.models import *
from database.users import session_scope
from routes.shared import bc_generator, ENTS


monitorings = Blueprint("monitorings", __name__)


class SCAN_INTERVALS:
    DEFAULT = 60
    TWO_HOURS = 2 * DEFAULT
    FOUR_HOURS = 4 * DEFAULT
    TWELVE_HOURS = 12 * DEFAULT
    DAY = 24 * DEFAULT
    WEEK = DAY * 7

    INTERVALS_DICT = OrderedDict(sorted({
        DEFAULT: "Hourly",
        TWO_HOURS: "Every 2 hours",
        FOUR_HOURS: "Every 4 hours",
        TWELVE_HOURS: "Every 12 hours",
        DAY: "Daily",
        WEEK: "Weekly"
    }.items()))


class REQUEST_INTERVALS:
    DEFAULT = 1
    FIVE_SEC = 5
    FIFTEEN_SEC = 15
    THIRTY_SEC = 30

    MIN = 60
    FIVE_MIN = MIN * 5
    FIFTEEN_MIN = MIN * 15
    THIRTY_MIN = MIN * 30

    INTERVALS_DICT = OrderedDict(sorted({
        DEFAULT: "1 second",
        FIVE_SEC: "5 seconds",
        FIFTEEN_SEC: "15 seconds",
        THIRTY_SEC: "30 seconds",

        MIN: "1 minute",
        FIVE_MIN: "5 minutes",
        FIFTEEN_MIN: "15 minutes",
        THIRTY_MIN: "30 minutes"
    }.items()))


@monitorings.route("/edit_monitoring/<project_id>/<entity_id>", methods=['GET'])
@login_required
def edit_monitoring(project_id, entity_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.EDIT_MONITORING, [ENTS.MONITORINGS])
    with session_scope(current_user.username, True) as session:
        current_products = session.query(Product).filter(Product.project_id == int(project_id)).all()
        current_sellers = session.query(Seller).filter(Seller.project_id == int(project_id)).all()
        monitoring_enabled = False
        enabled_scan_interval = SCAN_INTERVALS.DEFAULT
        enabled_request_interval = REQUEST_INTERVALS.DEFAULT

        if entity_id == 'new_entity':
            monitoring_products = {}
            monitoring_sellers = {}
            seller_self_id = None
            monitoring_name = "New Monitoring"

        else:
            current_monitoring = session.query(Monitoring).filter(Monitoring.id == entity_id).first()

            monitoring_products = session.query(MonitoringProduct, Product).filter(and_(MonitoringProduct.monitoring_id == entity_id,
                                                                                        MonitoringProduct.project_id == project_id,
                                                                                        MonitoringProduct.product_id == Product.id)).all()

            monitoring_sellers = session.query(MonitoringSeller, Seller).filter(and_(MonitoringSeller.monitoring_id == entity_id,
                                                                                     MonitoringSeller.project_id == project_id,
                                                                                     MonitoringSeller.seller_id == Seller.id,
                                                                                     MonitoringSeller.seller_id != current_monitoring.seller_self_id)).all()
            monitoring_name = current_monitoring.name
            monitoring_enabled = current_monitoring.enabled
            seller_self_id = current_monitoring.seller_self_id
            enabled_scan_interval=current_monitoring.update_interval
            enabled_request_interval=current_monitoring.request_interval

    return flask.render_template("monitoring/edit_monitoring.html",
                                 current_user=current_user.username,
                                 project_id=project_id,
                                 entity_id=entity_id,
                                 monitoring_products=monitoring_products,
                                 monitoring_sellers=monitoring_sellers,
                                 project_products=current_products,
                                 project_sellers=current_sellers,
                                 monitoring_name=monitoring_name,
                                 monitoring_enabled=monitoring_enabled,
                                 seller_self_id=seller_self_id,
                                 bc_data=bc_data,
                                 enabled_scan_interval=enabled_scan_interval,
                                 enabled_request_interval=enabled_request_interval,
                                 scan_intervals=SCAN_INTERVALS.INTERVALS_DICT,
                                 request_intervals=REQUEST_INTERVALS.INTERVALS_DICT,
                                 save_url=flask.url_for("monitorings.save_monitoring"),
                                 redirect_url=flask.url_for("monitorings.monitorings_view", project_id=project_id))


@monitorings.route("/monitorings_view/<project_id>", methods=['GET'])
@login_required
def monitorings_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.MONITORINGS)
    with session_scope(current_user.username, True) as session:
        current_monitorings = session.query(Monitoring).filter(Monitoring.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('monitorings.edit_monitoring', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('monitorings.delete_monitoring')
    entity_view_url = flask.url_for('monitorings.monitorings_view', project_id=project_id)
    view_entity = 'monitorings.monitoring_view_flat'
    edit_entity = 'monitorings.edit_monitoring'

    return flask.render_template("monitoring/monitorings_view.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 entities=current_monitorings,
                                 common_name="monitoring",
                                 new_entity_url=new_entity_url,
                                 delete_entity_url =delete_entity_url,
                                 entity_view_url=entity_view_url,
                                 edit_entity=edit_entity,
                                 view_entity=view_entity,
                                 bc_data=bc_data,
                                 create_ent_txt="Create monitoring")


@monitorings.route("/save_monitoring", methods=['POST'])
@login_required
def save_monitoring():
    request_json = flask.request.get_json()
    print(request_json)
    products = request_json['products']
    sellers = request_json['sellers']
    monitoring_name = request_json['name']
    monitoring_id = request_json['monitoring']
    project_id = int(request_json['project'])
    monitoring_enabled = request_json['enabled']

    update_interval = int(request_json['update_interval'])
    update_interval = update_interval if update_interval in SCAN_INTERVALS.INTERVALS_DICT else SCAN_INTERVALS.DEFAULT

    request_interval = int(request_json['request_interval'])
    request_interval = request_interval if request_interval in REQUEST_INTERVALS.INTERVALS_DICT else REQUEST_INTERVALS.DEFAULT

    seller_self = request_json['seller_self']
    seller_self = int(seller_self) if seller_self != "NONE" else None

    with session_scope(current_user.username) as session:

        seller_self_obj = session.query(Seller).filter(Seller.id == seller_self).first()

        if monitoring_id != 'new_entity':
            current_monitoring = session.query(Monitoring).filter(Monitoring.id == monitoring_id).first()
            current_monitoring.name = monitoring_name
            current_monitoring.enabled = monitoring_enabled
            current_monitoring.seller_self_id = seller_self
            current_monitoring.update_interval = update_interval
            current_monitoring.request_interval = request_interval
            current_monitoring.seller_self_name = None if seller_self_obj is None else seller_self_obj.name

            monitoring_products = session.query(MonitoringProduct).filter(MonitoringProduct.monitoring_id == monitoring_id)
            monitoring_sellers = session.query(MonitoringSeller).filter(MonitoringSeller.monitoring_id == monitoring_id)

            db_sellers_set = set()
            db_products_set = set()

            for product in monitoring_products:
                db_products_set.add(product.product_id)

            for seller in monitoring_sellers:
                db_sellers_set.add(seller.seller_id)

            request_products_set = set()
            request_sellers_set = set()

            prod_idmap = {}
            seller_idmap = {}

            for product in products:
                prod_id = int(product['id'])
                request_products_set.add(prod_id)
                prod_idmap[prod_id] = product

            for seller in sellers:
                sel_id = int(seller['id'])
                request_sellers_set.add(sel_id)
                seller_idmap[sel_id] = seller

            if seller_self_obj:
                request_sellers_set.add(seller_self_obj.id)
                seller_idmap[seller_self_obj.id] = {'id': seller_self_obj.id}

            products_to_remove = db_products_set - request_products_set
            sellers_to_remove = db_sellers_set - request_sellers_set

            for id in products_to_remove:
                session.query(MonitoringProduct).filter(MonitoringProduct.product_id == id).delete()

            for id in sellers_to_remove:
                session.query(MonitoringSeller).filter(MonitoringSeller.seller_id == id).delete()

            prod_id_to_insert = request_products_set - db_products_set
            sel_id_to_insert = request_sellers_set - db_sellers_set

            products = []
            sellers = []

            for pid in prod_id_to_insert:
                products.append(prod_idmap[pid])

            for sid in sel_id_to_insert:
                sellers.append(seller_idmap[sid])
        else:
            current_monitoring = Monitoring(name=monitoring_name,
                                            project_id=project_id,
                                            seller_self_id=seller_self,
                                            update_interval=update_interval,
                                            request_interval=request_interval,
                                            enabled=monitoring_enabled)

            session.add(current_monitoring)
            session.flush()
            monitoring_id = current_monitoring.id

        for product in products:
            session.add(MonitoringProduct(
                project_id=project_id,
                monitoring_id=monitoring_id,
                product_id=int(product['id']))
            )

        for seller in sellers:
            session.add(MonitoringSeller(
                project_id=project_id,
                monitoring_id=monitoring_id,
                seller_id=int(seller['id']))
            )

    return "OK"


@monitorings.route("/delete_monitoring", methods=['POST'])
@login_required
def delete_monitoring():
    request_js = flask.request.get_json()
    print(request_js)
    monitoring_id = request_js['id']
    project_id = request_js['project_id']
    with session_scope(current_user.username) as session:
        session.query(Monitoring).filter(Monitoring.id == monitoring_id).delete()
    return flask.redirect(flask.url_for("monitorings.monitorings_view", project_id=project_id))


@monitorings.route("/monitoring_view/<project_id>/<monitoring_id>", methods=['GET'])
@login_required
def monitoring_view(project_id, monitoring_id):
    with session_scope(current_user.username, True) as session:
        monitored_products = session.query(MonitoredProduct).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                                         MonitoredProduct.project_id == project_id)).all()

    view_products = {}
    for product in monitored_products:
        product_sellers = view_products.get(product.product_id)

        if not product_sellers:
            product_sellers = []
            view_products[product.product_id] = product_sellers

        product_sellers.append(product)

    print(view_products)

    return flask.render_template("monitoring/monitoring_view.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 monitoring_id=monitoring_id,
                                 monitored_products=view_products)


@monitorings.route("/edit_monitoring_object/<project_id>/<monitoring_id>/<product_id>/<seller_id>", methods=['GET'])
@login_required
def edit_monitoring_object(project_id, monitoring_id, product_id, seller_id):
    with session_scope(current_user.username, True) as session:
        product = session.query(Product).filter(Product.id == product_id).first()
        product_options = session.query(ProductOption).filter(ProductOption.product_id == product_id).all()
        seller = session.query(Seller).filter(Seller.id == seller_id).first()
        parsers = session.query(Parser).filter(Parser.project_id == project_id).all()

        monitored_product = session.query(MonitoredProduct).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                                        MonitoredProduct.product_id == product_id,
                                                                        MonitoredProduct.project_id == project_id,
                                                                        MonitoredProduct.seller_id == seller_id)).first()

        if monitored_product:
            monitored_options = session.query(MonitoredOption).filter(and_(MonitoredOption.monitored_product_id == monitored_product.id)).all()
            bc_operation = ENTS.EDIT_MONITORING_OBJECT
        else:
            bc_operation = ENTS.CREATE_MONITORING_OBJECT
            monitored_options = []

        monitored_options_id_to_data = {}

        for option in monitored_options:
            monitored_options_id_to_data[option.option_id] = option

        bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, bc_operation,
                                                    [ENTS.MONITORINGS], Monitoring, monitoring_id, ENTS.MONITORING)

    return flask.render_template("monitoring/edit_monitoring_object.html",
                                 current_user=current_user.username,
                                 project_id=project_id,
                                 monitoring_id=monitoring_id,
                                 product=product,
                                 seller=seller,
                                 product_options=product_options,
                                 project_parsers=parsers,
                                 monitored_product=monitored_product,
                                 options_id_to_data=monitored_options_id_to_data,
                                 save_url=flask.url_for("monitorings.save_monitoring"),
                                 bc_data=bc_data,
                                 redirect_url=flask.url_for("monitorings.monitoring_view_flat", project_id=project_id, monitoring_id=monitoring_id))


@monitorings.route("/delete_monitoring_object", methods=['POST'])
@login_required
def delete_monitoring_object():
    request_js = flask.request.get_json()
    monitoring_id = request_js['monitoring_id']
    project_id = request_js['project_id']
    product_id = request_js['product_id']
    seller_id = request_js['seller_id']
    with session_scope(current_user.username) as session:
        session.query(MonitoredProduct).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                    MonitoredProduct.product_id == product_id,
                                                    MonitoredProduct.project_id == project_id,
                                                    MonitoredProduct.seller_id == seller_id)).delete()
    return "OK"


def format_parser_parameter(param_string):
    return bytearray(json.dumps(param_string), "utf-8").decode('unicode-escape')


def get_option_data(option):
    option_id = int(option['option_id'])
    option_parser_id = option['parser_id']
    option_parser_id = int(option_parser_id) if option_parser_id != 'NONE' else None
    option_parser_param = option['params']
    option_parser_param = format_parser_parameter(option_parser_param) if option_parser_param else None

    return option_id, option_parser_id, option_parser_param


@monitorings.route("/save_monitoring_object", methods=['POST'])
@login_required
def save_monitoring_object():
    request_js = flask.request.get_json()
    product_id = int(request_js['product_id'])
    seller_id = int(request_js['seller_id'])
    monitoring_id = int(request_js['monitoring_id'])
    project_id = int(request_js['project_id'])
    basic_parser = request_js['basic_parser']

    with session_scope(current_user.username) as session:
        monitored_product = session.query(MonitoredProduct).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                                        MonitoredProduct.product_id == product_id,
                                                                        MonitoredProduct.project_id == project_id,
                                                                        MonitoredProduct.seller_id == seller_id)).first()

        basic_parser_id = basic_parser['id']
        basic_parser_id = int(basic_parser_id) if basic_parser_id != 'NONE' else None
        parser_parameter = basic_parser['params']
        parser_parameter = format_parser_parameter(parser_parameter) if parser_parameter else None
        monitor_url = request_js['monitor_url']
        monitor_url = monitor_url if monitor_url else None
        monitored_options = request_js['options']

        if not monitored_product:
            monitoring_entities = session.query(MonitoringProduct, MonitoringSeller).filter(and_(MonitoringProduct.product_id == product_id,
                                                                                                 MonitoringSeller.seller_id == seller_id)).first()

            monitored_product = MonitoredProduct(project_id=project_id,
                                                 monitoring_id=monitoring_id,
                                                 seller_id=seller_id,
                                                 product_id=product_id,
                                                 parser_id=basic_parser_id,
                                                 monitoring_product_id=monitoring_entities[0].id,
                                                 monitoring_seller_id=monitoring_entities[1].id,
                                                 parser_parameter=parser_parameter,
                                                 url=monitor_url
                                                 )
            session.add(monitored_product)
            session.flush()

            for option in monitored_options:
                id, parser, param = get_option_data(option)
                session.add(MonitoredOption(monitored_product_id=monitored_product.id,
                                            option_id=id,
                                            project_id=project_id,
                                            monitoring_id=monitoring_id,
                                            parser_id=parser,
                                            parser_parameter=param))

        else:
            monitored_product.parser_id = basic_parser_id
            monitored_product.parser_parameter = parser_parameter
            monitored_product.url = monitor_url

            for option in monitored_options:
                id, parser, param = get_option_data(option)
                db_option = session.query(MonitoredOption).filter(and_(MonitoredOption.option_id == id,
                                                                       MonitoredOption.monitored_product_id == monitored_product.id)).first()
                db_option.parser_id = parser
                db_option.parser_parameter = param

    return "OK"


@monitorings.route("/monitoring_view_flat/<project_id>/<monitoring_id>", methods=['GET'])
@login_required
def monitoring_view_flat(project_id, monitoring_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, None, [ENTS.MONITORINGS],
                                                Monitoring, monitoring_id, ENTS.MONITORING)
    with session_scope(current_user.username, True) as session:
        monitoring = session.query(Monitoring).filter(Monitoring.id == monitoring_id).first()
        monitored_products = session.query(MonitoredProduct).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                                         MonitoredProduct.project_id == project_id)).all()

        all_monintoring_products = session.query(MonitoringProduct, Product).filter(and_(MonitoringProduct.monitoring_id == monitoring_id,
                                                                                         MonitoringProduct.project_id == project_id,
                                                                                         MonitoringProduct.product_id == Product.id)).all()
        all_monitoring_sellers = session.query(MonitoringSeller, Seller).filter(and_(MonitoringSeller.monitoring_id == monitoring_id,
                                                                                     MonitoringSeller.project_id == project_id,
                                                                                     MonitoringSeller.seller_id == Seller.id,
                                                                                     MonitoringSeller.seller_id != monitoring.seller_self_id)).all()

        pids_to_sids = {}
        for mon_object in monitored_products:
            sids = pids_to_sids.get(mon_object.product_id)
            if not sids:
                sids = set()
                pids_to_sids[mon_object.product_id] = sids
            sids.add(mon_object.seller_id)

    return flask.render_template("monitoring/monitoring_view_flat.html",
                                 current_user=current_user.username,
                                 project_id=project_id,
                                 monitoring_id=monitoring_id,
                                 monitoring_sellers=all_monitoring_sellers,
                                 monitoring_products=all_monintoring_products,
                                 seller_self_id=monitoring.seller_self_id,
                                 bc_data=bc_data,
                                 remove_url=flask.url_for("monitorings.delete_monitoring_object"),
                                 pids_to_sids=pids_to_sids)
