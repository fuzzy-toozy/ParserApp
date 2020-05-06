import json
import flask
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, and_
import sqlalchemy
from flask_login import LoginManager, login_required, logout_user, current_user, login_user
from flask_session import Session

from collections import OrderedDict
from multiprocessing import Process, Queue
from datetime import timedelta

from common import parsing
import database.entities as db_ent
from database.database import flask_db, DB_ROOT
from database.users import create_admin, user_db_mgr, session_scope
from database.models import *
from common.forms import LoginForm, ProjectForm, SellerForm, ParserForm
from common.settings import SECRET_KEY, PARSERS_DIR

from common.scanning import MonitoringScanner, ScanningResult, ScanProcessor

app = Flask(__name__, root_path="/home/fuzzy/shit/gledos/gachi_parser/")
login_manager = LoginManager()

print("PATH: %s" % app.root_path)


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


class ENTS:
    PROJECT = 0x50
    MONITORING = 0x51
    PRODUCT = 0x52
    SELLER = 0x53
    PARSER = 0x54
    REPORT = 0x55

    SELLERS = 0x100
    PRODUCTS = 0x101
    MONITORINGS = 0x102
    PROJECTS = 0x103
    PARSERS = 0x104
    REPORTS = 0x105

    EDIT_MONITORING = 0x200
    EDIT_SELLER = 0x201
    EDIT_PRODUCT = 0x202
    EDIT_PARSER = 0x203
    EDIT_PROJECT = 0x204
    EDIT_MONITORING_OBJECT = 0x205
    EDIT_REPORT = 0x206

    CREATE_MONITORING = 0x300
    CREATE_SELLER = 0x301
    CREATE_PRODUCT = 0x302
    CREATE_PARSER = 0x303
    CREATE_PROJECT = 0x304
    CREATE_MONITORING_OBJECT = 0x305
    CREATE_REPORT = 0x306


class BreadcrumbsGenerator:
    def __init__(self):
        self.api_names = {
                            ENTS.PROJECTS: ("Projects", "main_form"),
                            ENTS.MONITORINGS: ("Monitorings", "monitorings_view"),
                            ENTS.PARSERS: ("Parsers", "parsers_view"),
                            ENTS.SELLERS: ("Sellers", "sellers_view"),
                            ENTS.PRODUCTS: ("Products", "products_view"),
                            ENTS.PROJECT: ("Project", "project_view"),
                            ENTS.MONITORING: ("monitoring_id", "monitoring_view_flat"),
                            ENTS.REPORTS: ("Reports", "reports_view"),
                            ENTS.EDIT_MONITORING: ("Edit monitoring", None),
                            ENTS.EDIT_SELLER: ("Edit seller", None),
                            ENTS.EDIT_PRODUCT: ("Edit product", None),
                            ENTS.EDIT_PARSER: ("Edit parser", None),
                            ENTS.EDIT_PROJECT: ("Edit project", None),
                            ENTS.EDIT_MONITORING_OBJECT: ("Edit monitoring object", None),
                            ENTS.EDIT_REPORT: ("Edit report", None),
                            ENTS.CREATE_MONITORING: ("Create monitoring", None),
                            ENTS.CREATE_SELLER: ("Create seller", None),
                            ENTS.CREATE_PRODUCT: ("Create product", None),
                            ENTS.CREATE_PROJECT: ("Create project", None),
                            ENTS.CREATE_PARSER: ("Create parser", None),
                            ENTS.CREATE_MONITORING_OBJECT: ("Create monitoring object", None),
                            ENTS.CREATE_REPORT: ("Create report", None)
        }

    def init_user(self, user_name):
        self.user_name = user_name

    def get_breadcrumbs_data(self, user_name, project_id=None, last_id=None, views_list=None, ent_model=None, ent_db_id=None, ent_ep_id=None):
        bc_result = []

        pr_name, pr_endp = self.api_names[ENTS.PROJECTS]
        bc_result.append((pr_name, flask.url_for(pr_endp)))

        if last_id == ENTS.PROJECTS:
            return bc_result

        with session_scope(user_name) as session:

            if project_id:
                current_project = session.query(Project).filter(Project.id == project_id).first()
                _, project_endp = self.api_names[ENTS.PROJECT]
                bc_result.append((current_project.name, flask.url_for(project_endp, project_id=project_id)))

            if views_list:
                for view_id in views_list:
                    view_name, view_endpoint = self.api_names[view_id]
                    bc_result.append((view_name, flask.url_for(view_endpoint, project_id=project_id)))

            if ent_db_id:
                current_entity = session.query(ent_model).filter(and_(ent_model.project_id == project_id,
                                                                      ent_model.id == ent_db_id)).first()
                ent_name_id, entity_endp = self.api_names[ent_ep_id]
                template_data = { "project_id": project_id,
                                  ent_name_id: ent_db_id }

                bc_result.append((current_entity.name, flask.url_for(entity_endp, **template_data)))

            if last_id:
                bc_result.append((self.api_names[last_id][0], "#"))

            return bc_result


bc_generator = BreadcrumbsGenerator()


def get_ent_by_id(session, entity, ent_id, project_id):
    db_ent = session.query(entity).filter(and_(entity.id == ent_id,
                                               entity.project_id == project_id)).first()
    return db_ent


def _fk_pragma_on_connect(dbapi_con, con_record):
    dbapi_con.execute('pragma foreign_keys=ON')


class ServerApp:
    def __init__(self, flask_app, flask_login_mgr):
        self.flask_app = flask_app
        self.login_manager = flask_login_mgr
        self.root_dir = None
        self.db = None
        self.session = Session()
        self.scan_processor = ScanProcessor()

    def init(self, root_dir):
        self.flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.flask_app.config["SECRET_KEY"] = SECRET_KEY
        self.flask_app.secret_key = SECRET_KEY
        self.flask_app.config["SESSION_TYPE"] = "sqlalchemy"
        self.flask_app.config["SESSION_SQLALCHEMY"] = flask_db
        self.root_dir = root_dir

        self.session.init_app(self.flask_app)
        self.login_manager.init_app(self.flask_app)
        self.init_db()
        self.run_scan_workers()

    def run(self):
        self.flask_app.run()

    def finish(self):
        self.scan_processor.stop_scan_workers()

    def run_scan_workers(self):
        if not self.scan_processor.is_initialised():
            with app.app_context():
                all_users = User.query.all()
                users_set = set()
                for user in all_users:
                    users_set.add(user.username)
                self.scan_processor.init_users(users_set)
            self.scan_processor.run_scan()

    def init_db(self):
        self.flask_app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///%s/db_data/%s.db" % (self.root_dir, "main_app.db")
        self.flask_app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"
        flask_db.init_app(app)

        with app.app_context():
            flask_db.create_all()
            create_admin()

    def add_scan_object(self, project_id, monitoring_id, user):
        self.scan_processor.add_scan_object(project_id, monitoring_id, user)

    def get_scan_stats(self, user):
        return self.scan_processor.get_stats(user)

    def create_db_tables(self, user):
        self.db_engine = sqlalchemy.create_engine("sqlite:///%s/db_data/%s.db" % (self.root_dir, user))
        #event.listen(self.db_engine, 'connect', _fk_pragma_on_connect)

        metadata = MetaData()
        try:
            metadata.create_all(self.db_engine)
            print("Tables created")
        except Exception as e:
            print("Error occurred during Table creation!")
            print(e)


main_app = ServerApp(app, login_manager)


@app.before_request
def set_session_timeout():
    flask.session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=60)


@app.route("/check_ajax", methods=['POST'])
def check():
    request_json = flask.request.get_json()
    print(request_json)

    main_app.create_db_tables("faggot")

    query = User.query.filter(User.username == "Admin").first()

    return "<p> %s, %s, %s</p>" % (query.username, query.created, query.admin)


@login_manager.user_loader
def load_user(user_id):
    """Check if user is logged-in on every page load."""
    if user_id is not None:
        return User.query.get(user_id)
    return None


@login_manager.unauthorized_handler
def unauthorized():
    flask.flash('You must be logged in to view that page.')
    return flask.redirect(flask.url_for("login_page"))


@app.route("/logout")
@login_required
def logout_page():
    logout_user()
    return flask.redirect(flask.url_for("login_page"))


@app.route('/main', methods=['GET'])
@login_required
def main_form():
    bc_generator.init_user(current_user.username)
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username)

    with session_scope(current_user.username) as session:
        user_projects = session.query(Project).all()

        if user_projects and len(user_projects) == 0:
            user_projects = None
        ctx = {"current_user": current_user.username, "projects": user_projects, "bc_data": bc_data}
        return flask.render_template("project/projects.html", **ctx)


@app.route("/create_project", methods=['GET', 'POST'])
@login_required
def create_project():
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, None, ENTS.CREATE_PROJECT)
    if flask.request.method == 'GET':
        return flask.render_template("project/create_project.html", current_user=current_user.username, form=ProjectForm(), bc_data=bc_data)
    else:
        project_name = flask.request.form.get('name')
        with session_scope(current_user.username) as session:
            session.add(Project(name=project_name))
        return flask.redirect(flask.url_for("main_form"))


@app.route("/project_settings/<project_id>", methods=['GET', 'POST'])
@login_required
def project_settings(project_id):
    if flask.request.method == 'GET':
        bc_data = bc_generator.get_breadcrumbs_data(current_user.username, None, ENTS.EDIT_PROJECT)
        return flask.render_template("project/project_settings.html", current_user=current_user.username,
                                     form=ProjectForm(), project_id=project_id, bc_data=bc_data)
    else:
        with session_scope(current_user.username) as session:
            current_proj = session.query(Project).filter(Project.id == project_id).first()
            if current_proj:
                current_proj.name = flask.request.form.get('name')
            return flask.redirect(flask.url_for("main_form"))


@app.route("/project_view/<project_id>", methods=['GET'])
@login_required
def project_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id)
    ctx = {"current_user": current_user.username,
           "project_id": project_id,
           "bc_data": bc_data}
    return flask.render_template("project/project_view.html", **ctx)


@app.route("/delete_project", methods=['POST'])
@login_required
def delete_project():
    request_js = flask.request.get_json()

    with session_scope(current_user.username) as session:
        session.query(Project).filter(Project.id == int(request_js['name'])).delete()

    return flask.redirect(flask.url_for("main_form"))


@app.route("/products_view/<project_id>", methods=['GET'])
@login_required
def products_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.PRODUCTS)
    if flask.request.method == 'GET':
        with session_scope(current_user.username) as session:
            current_products = session.query(Product).filter(Product.project_id == int(project_id)).all()
            return flask.render_template("product/products_view.html",
                                         current_user=current_user.username,
                                         project_id=project_id,
                                         products=current_products,
                                         bc_data=bc_data)


@app.route("/edit_product/<project_id>/<product_id>", methods=['GET'])
@login_required
def edit_product(project_id, product_id):
    if product_id != 'new_product':
        with session_scope(current_user.username, True) as session:
            current_product = session.query(Product).filter(Product.id == int(product_id)).first()
            current_product_name = current_product.name
            current_product_opts = session.query(ProductOption).filter(ProductOption.product_id == int(product_id)).all()
            bc_action_id = ENTS.EDIT_PRODUCT
    else:
        current_product_name = "New Product"
        current_product_opts = []
        bc_action_id = ENTS.CREATE_PRODUCT

    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, bc_action_id, [ENTS.PRODUCTS])
    return flask.render_template("product/edit_product.html",
                                 current_user=current_user.username,
                                 product_options=current_product_opts,
                                 product_name=current_product_name,
                                 project_id=project_id,
                                 product_id=product_id,
                                 bc_data=bc_data)


@app.route("/save_product", methods=['POST'])
@login_required
def save_product():
    request_json = flask.request.get_json()
    project_id = int(request_json['project_id'])
    product_id = request_json['product_id']
    product_name = request_json['name']
    product_options = request_json['options']

    with session_scope(current_user.username) as session:

        if product_id != 'new_product':
            current_product = session.query(Product).filter(Product.id == product_id).first()
            current_product.name = product_name

            stored_options_db = session.query(ProductOption).filter(ProductOption.product_id == product_id).all()

            id_to_option_stored = {}
            stored_options_set = set()

            for option in stored_options_db:
                id_to_option_stored[option.id] = option
                stored_options_set.add(option.id)

            id_to_option_received = {}
            received_existing_options_set = set()
            options_to_insert = []
            for option_name, option_id in product_options['rest'].items():
                if int(option_id) != -1:
                    received_existing_options_set.add(int(option_id))
                    id_to_option_received[int(option_id)] = option_name
                else:
                    options_to_insert.append(option_name)

            options_to_update = received_existing_options_set.intersection(stored_options_set)

            for option_id in options_to_update:
                id_to_option_stored[option_id].name = id_to_option_received[option_id]

            for option_id in product_options["deleted"]:
                session.query(ProductOption).filter(ProductOption.id == int(option_id)).delete()

            for option_name in options_to_insert:
                new_option = ProductOption(name=option_name, product_id=product_id, project_id=project_id)
                session.add(new_option)
                session.flush()
                monitored_products = session.query(MonitoredProduct).filter(MonitoredProduct.product_id == product_id,
                                                                            MonitoredProduct.project_id == project_id).all()
                if monitored_products:
                    for mon_product in monitored_products:
                        session.add(MonitoredOption(option_id=new_option.id,
                                                    project_id=project_id,
                                                    monitoring_id=mon_product.monitoring_id,
                                                    monitored_product_id=mon_product.id))


            current_product.options = json.dumps(product_options)
        else:
            new_product = Product(name=product_name, project_id=project_id)
            session.add(new_product)
            session.flush()

            for option_name, option_id in product_options['rest'].items():
                session.add(ProductOption(name=option_name, product_id=new_product.id, project_id=project_id))

    return "OK"


@app.route("/delete_product", methods=['POST'])
@login_required
def delete_product():
    request_json = flask.request.get_json()
    product_id = int(request_json['product_id'])
    project_id = int(request_json['project_id'])

    with session_scope(current_user.username) as session:
        session.query(Product).filter(Product.id == product_id).delete()

    return flask.redirect(flask.url_for("products_view", project_id=project_id))


@app.route("/edit_seller/<project_id>/<entity_id>", methods=['GET', 'POST'])
@login_required
def edit_seller(project_id, entity_id):
    if flask.request.method == 'GET':
        if entity_id == "new_entity":
            bc_op = ENTS.CREATE_SELLER
        else:
            bc_op = ENTS.EDIT_SELLER

        bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, bc_op, [ENTS.SELLERS])

        return flask.render_template("seller/edit_seller.html",
                                     current_user=current_user.username,
                                     form=SellerForm(),
                                     entity_id=entity_id,
                                     project_id=project_id,
                                     bc_data=bc_data,
                                     entity_view_url=flask.url_for('sellers_view', project_id=project_id),
                                     save_entity_url=flask.url_for('edit_seller', project_id=project_id,
                                                                   entity_id=entity_id))
    else:
        with session_scope(current_user.username) as session:
            if entity_id == 'new_entity':
                session.add(Seller(name=flask.request.form.get('name'), project_id=int(project_id)))
            else:
                current_seller = session.query(Seller).filter(Seller.id == entity_id).first()
                current_seller.name = flask.request.form.get('name')

        return flask.redirect(flask.url_for("sellers_view",
                                            project_id=project_id))


@app.route("/sellers_view/<project_id>", methods=['GET'])
@login_required
def sellers_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.SELLERS)
    with session_scope(current_user.username, True) as session:
        current_sellers = session.query(Seller).filter(Seller.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('edit_seller', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('delete_seller')
    entity_view_url = flask.url_for('sellers_view', project_id=project_id)
    edit_entity = 'edit_seller'

    return flask.render_template("seller/sellers_view.html",
                                 current_user=current_user.username,
                                 project_id=project_id,
                                 entities=current_sellers,
                                 common_name="seller",
                                 new_entity_url=new_entity_url,
                                 delete_entity_url =delete_entity_url,
                                 entity_view_url=entity_view_url,
                                 edit_entity=edit_entity,
                                 bc_data=bc_data,
                                 create_ent_txt="Create seller")


@app.route("/delete_seller", methods=['POST'])
@login_required
def delete_seller():
    request_js = flask.request.get_json()
    print(request_js)
    seller_id = request_js['id']
    project_id = request_js['project_id']
    with session_scope(current_user.username) as session:
        session.query(Seller).filter(Seller.id == seller_id).delete()

    return flask.redirect(flask.url_for("sellers_view", project_id=project_id))


@app.route("/parsers_view/<project_id>", methods=['GET'])
@login_required
def parsers_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.PARSERS)
    with session_scope(current_user.username, True) as session:
        current_sellers = session.query(Parser).filter(Parser.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('edit_parser', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('delete_parser')
    entity_view_url = flask.url_for('parsers_view', project_id=project_id)
    edit_entity = 'edit_parser'

    return flask.render_template("parser/parsers_view.html",
                                 current_user=current_user.username,
                                 project_id=project_id,
                                 entities=current_sellers,
                                 common_name="parser",
                                 new_entity_url=new_entity_url,
                                 delete_entity_url =delete_entity_url,
                                 entity_view_url=entity_view_url,
                                 edit_entity=edit_entity,
                                 bc_data=bc_data,
                                 create_ent_txt="Create parser")


def validate_parser(parser_file, parser_name, parsers_dir):
    response_dict = {}
    parser_code = None
    validation_res = False
    try:
        parser_code = parser_file.read()
    except Exception as ex:
        response_dict["result"] = "ERROR"
        response_dict["message"] = str(ex)

    if parser_code:
        parser_code = parser_code.decode("utf-8")
        parser_module, err_msg, parser_code = parsing.make_parser_module(parser_code, parser_name, parsers_dir)
        if parser_module:
            validation_res, err = parsing.check_required_function(parser_module)
            if validation_res:
                response_dict["result"] = "OK"
                response_dict["message"] = "Parser python code is valid"
            else:
                response_dict["result"] = "ERROR"
                response_dict["message"] = "Parser has no function 'parse_page'"
        else:
            response_dict["result"] = "ERROR"
            response_dict["message"] = err_msg

    return validation_res, parser_code, response_dict


@app.route("/edit_parser/<project_id>/<entity_id>", methods=['GET', 'POST'])
@login_required
def edit_parser(project_id, entity_id):
    if flask.request.method == 'GET':
        entity_view_url = flask.url_for('parsers_view', project_id=project_id)
        save_entity_url = flask.url_for('edit_parser', project_id=project_id, entity_id=entity_id)
        test_parser_url = flask.url_for('test_parser_view', project_id=project_id, parser_id=entity_id)

        current_parser = None
        parser_name = None
        parser_code = None

        if entity_id == "new_entity":
            bc_operation = ENTS.CREATE_PARSER
        else:
            with session_scope(current_user.username, True) as session:
                current_parser = session.query(Parser).filter(Parser.id == int(entity_id)).first()
            parser_name = current_parser.name
            bc_operation = ENTS.EDIT_PARSER
            if current_parser.code:
                parser_code = current_parser.code

        bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, bc_operation, [ENTS.PARSERS])

        return flask.render_template("parser/edit_parser.html",
                                     current_user=current_user.username,
                                     parser_code=parser_code,
                                     entity_id=entity_id,
                                     project_id=project_id,
                                     entity_view_url=entity_view_url,
                                     save_entity_url=save_entity_url,
                                     test_parser_url=test_parser_url,
                                     current_parser=current_parser,
                                     bc_data=bc_data,
                                     parser_name=parser_name)

    else:
        response_dict = {}
        form_params = json.loads(flask.request.form.get('parameters'))
        parser_name = form_params['name']
        parser_file = flask.request.files['parser-file']
        if parser_file:
            validation_res, parser_code, response_dict = validate_parser(parser_file, parser_name, PARSERS_DIR)
            if not validation_res:
                return flask.jsonify(response_dict)
        else:
            parser_code = None

        with session_scope(current_user.username) as session:
            if entity_id == 'new_entity':
                session.add(Parser(name=parser_name, code=parser_code, project_id=int(project_id)))
            else:
                current_parser = session.query(Parser).filter(Parser.id == entity_id).first()
                current_parser.name = parser_name
                if parser_code:
                    current_parser.code = parser_code

        response_dict['result'] = 'OK'
        result = flask.jsonify(response_dict)
        return result


@app.route("/delete_parser", methods=['POST'])
@login_required
def delete_parser():
    request_js = flask.request.get_json()
    print(request_js)
    parser_id = request_js['id']
    project_id = request_js['project_id']
    session, ssc = user_db_mgr.get_user_db_session(current_user.username)
    session.query(Parser).filter(Parser.id == parser_id).delete()
    ssc.commit()
    return flask.redirect(flask.url_for("parsers_view", project_id=project_id))


@app.route("/test_parser/<project_id>/<parser_id>", methods=['POST'])
@login_required
def test_parser(project_id, parser_id):
    parser_url = flask.request.form.get('parser_url')
    parser_parameter = flask.request.form.get('parser_parameter')

    with session_scope(current_user.username, True) as session:
        current_parser = session.query(Parser).filter(and_(Parser.id == parser_id, Parser.project_id == project_id)).first()

    parser_exec_ok = False
    parser_code = None

    try:
        parser_code = current_parser.code if current_parser.code else None
        decode_failure = False
    except Exception as ex:
        decode_failure = True
        parser_result = str(ex)
        label_message = "Couldn't read parser code as utf8"

    if parser_code:
        page_dom, parser_result = parsing.get_page_dom(parser_url)
        if page_dom is None:
            label_message = "Couldn't load DOM"
        else:
            rescode, parser_result, label_message, parser_code = parsing.do_parse(current_parser,
                                                                                  parser_parameter, page_dom)
            parser_exec_ok = rescode == parsing.ParsingResult.OK
    elif decode_failure:
        pass
    else:
        parser_result = "No parser code supplied"

    return flask.render_template("parser/test_parser.html", current_user=current_user.username,
                                 label_message=label_message,
                                 parser_exec_ok=parser_exec_ok,
                                 parser_result=parser_result,
                                 current_parser=current_parser,
                                 parser_code=parser_code,
                                 project_id=project_id)


@app.route("/test_parser_view/<project_id>/<parser_id>", methods=['GET'])
@login_required
def test_parser_view(project_id, parser_id):
    with session_scope(current_user.username, True) as session:
        current_parser = session.query(Parser).filter(and_(Parser.id == parser_id, Parser.project_id == project_id)).first()
    if current_parser and current_parser.code:
        parser_code = current_parser.code
    else:
        parser_code = None
    submit_url = flask.url_for("test_parser", project_id=project_id, parser_id=parser_id)
    return flask.render_template("parser/test_parser_view.html", current_user=current_user.username,
                                 current_parser=current_parser,
                                 parser_code=parser_code,
                                 project_id=project_id,
                                 submit_url=submit_url)


@app.route("/edit_monitoring/<project_id>/<entity_id>", methods=['GET'])
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
                                 save_url=flask.url_for("save_monitoring"),
                                 redirect_url=flask.url_for("monitorings_view", project_id=project_id))


@app.route("/monitorings_view/<project_id>", methods=['GET'])
@login_required
def monitorings_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.MONITORINGS)
    with session_scope(current_user.username, True) as session:
        current_monitorings = session.query(Monitoring).filter(Monitoring.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('edit_monitoring', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('delete_monitoring')
    entity_view_url = flask.url_for('monitorings_view', project_id=project_id)
    view_entity = 'monitoring_view_flat'
    edit_entity = 'edit_monitoring'

    return flask.render_template("monitoring/monitorings_view.html",
                                 current_user=current_user.username,
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


@app.route("/save_monitoring", methods=['POST'])
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


@app.route("/delete_monigoring", methods=['POST'])
@login_required
def delete_monitoring():
    request_js = flask.request.get_json()
    print(request_js)
    monitoring_id = request_js['id']
    project_id = request_js['project_id']
    with session_scope(current_user.username) as session:
        session.query(Monitoring).filter(Monitoring.id == monitoring_id).delete()
    return flask.redirect(flask.url_for("monitorings_view", project_id=project_id))


@app.route("/monitoring_view/<project_id>/<monitoring_id>", methods=['GET'])
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
                                  current_user=current_user.username,
                                  project_id=project_id,
                                  monitoring_id=monitoring_id,
                                  monitored_products=view_products)


@app.route("/edit_monitoring_object/<project_id>/<monitoring_id>/<product_id>/<seller_id>", methods=['GET'])
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
                                 save_url=flask.url_for("save_monitoring"),
                                 bc_data=bc_data,
                                 redirect_url=flask.url_for("monitoring_view_flat", project_id=project_id, monitoring_id=monitoring_id))


@app.route("/delete_monitoring_object", methods=['POST'])
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


@app.route("/save_monitoring_object", methods=['POST'])
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


@app.route("/monitoring_view_flat/<project_id>/<monitoring_id>", methods=['GET'])
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
                                 remove_url=flask.url_for("delete_monitoring_object"),
                                 pids_to_sids=pids_to_sids)


@app.route("/force_scan/<project_id>/<entity_id>", methods=['GET'])
@login_required
def force_scan(project_id, entity_id):
    with session_scope(current_user.username) as session:
        monitoring_products_and_parsers = session.query(MonitoredProduct,
                                                        Parser,
                                                        Product,
                                                        Seller).filter(and_(MonitoredProduct.monitoring_id == entity_id,
                                                                            MonitoredProduct.project_id == project_id,
                                                                            Product.id == MonitoredProduct.product_id,
                                                                            Seller.id == MonitoredProduct.seller_id)).outerjoin(Parser,
                                                                                                                                Parser.id == MonitoredProduct.parser_id).all()

        scan_results = []
        for mon_product, parser, product, seller in monitoring_products_and_parsers:
            parsing_results = {"product_name": product.name, "seller_name": seller.name}
            scan_results.append(parsing_results)
            base_parsing_result = {}
            parsing_results["base"] = base_parsing_result
            options_results = []
            parsing_results["options"] = options_results

            page_dom, parser_result = parsing.get_page_dom(mon_product.url)
            if page_dom is None:
                base_parsing_result["status"] = parsing.ParsingResult.DOM_FAILED
                base_parsing_result["message"] = parser_result
                continue
            else:
                parser_exec_status, parser_result, _, _ = parsing.do_parse(parser, mon_product.parser_parameter, page_dom)
                base_parsing_result["status"] = parser_exec_status
                base_parsing_result["message"] = parser_result

            monitored_options_data = session.query(MonitoredOption,
                                                   Parser,
                                                   ProductOption).filter(and_(MonitoredOption.monitored_product_id == mon_product.id,
                                                                              MonitoredOption.project_id == project_id,
                                                                              ProductOption.id == MonitoredOption.option_id)).outerjoin(Parser,
                                                                                                                                        Parser.id == MonitoredOption.parser_id).all()

            if not monitored_options_data:
                continue

            for monitored_option, option_parser, product_option in monitored_options_data:
                option_parsing_results = {"name": product_option.name}
                options_results.append(option_parsing_results)
                option_parser_exec_status, option_parser_result, _, _ = parsing.do_parse(option_parser, monitored_option.parser_parameter, page_dom)
                option_parsing_results["status"] = option_parser_exec_status
                option_parsing_results["message"] = option_parser_result

    return flask.jsonify(scan_results)

def do_gay_stuff(pqueue):
    result = ScanningResult.UNKNOWN
    while True:
        scaner = pqueue.get()         # Read from the queue and do nothing
        print("init: %s" % str(scaner.init_scan_data()))
        while result != ScanningResult.FINISHED:
            print("AAAAAAAA\n")
            result, msg = scaner.scan_product()
        break

@app.route("/force_scan_test/<project_id>/<entity_id>", methods=['GET'])
@login_required
def force_scan_test(project_id, entity_id):
    main_app.add_scan_object(project_id, entity_id, current_user.username)
    return flask.jsonify(main_app.get_scan_stats(current_user.username))

@app.route("/scan_stats", methods=['GET'])
@login_required
def scan_stats():
    return flask.jsonify(main_app.get_scan_stats(current_user.username))


@app.route("/report_view/<project_id>/<entity_id>", methods=['GET'])
@login_required
def report_view(project_id, entity_id):
    return "<b>OK</b>"


@app.route("/edit_report/<project_id>/<entity_id>", methods=['GET'])
@login_required
def edit_report(project_id, entity_id):
    return "<b>OK</b>"


@app.route("/delete_report", methods=['POST'])
@login_required
def delete_report(project_id, report_id):
    return "<b>OK</b>"


@app.route("/reports_view/<project_id>", methods=['GET'])
@login_required
def reports_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.REPORTS)
    session, ssc = user_db_mgr.get_user_db_session(current_user.username)
    current_reports = None

    new_entity_url = flask.url_for('edit_report', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('delete_report')
    entity_view_url = flask.url_for('reports_view', project_id=project_id)
    view_entity = 'report_view'
    edit_entity = 'edit_report'

    return flask.render_template("report/reports_view.html",
                                 current_user=current_user.username,
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



@app.route("/sellers_table_data/<project_id>/<monitoring_id>/<product_id>", methods=['GET'])
@login_required
def sellers_table_data(project_id, monitoring_id, product_id):
    with session_scope(current_user.username, True) as session:
        current_monitoring = session.query(Monitoring).filter(Monitoring.id == monitoring_id).first()
        monitored_products = session.query(MonitoredProduct).filter(and_(MonitoredProduct.monitoring_id == monitoring_id,
                                                                        MonitoredProduct.project_id == project_id,
                                                                        MonitoredProduct.product_id == product_id)).all()

    return flask.render_template("product/product_sellers.html",
                                 seller_self="GAY",
                                 product_id=product_id,
                                 products_array=monitored_products)


@app.route("/gaytst", methods=['GET'])
@login_required
def gaytst():
    return flask.render_template("gaytst.html")


@app.route("/getshit", methods=['GET'])
def getshit():
    return flask.jsonify({
  "data": [
    {
      "id": "1",
      "name": "Tiger Nixon",
      "position": "System Architect",
      "salary": "$320,800",
      "start_date": "2011/04/25",
      "office": "Edinburgh",
      "extn": "5421"
    },
    {
      "id": "2",
      "name": "Garrett Winters",
      "position": "Accountant",
      "salary": "$170,750",
      "start_date": "2011/07/25",
      "office": "Tokyo",
      "extn": "8422"
    },
    {
      "id": "3",
      "name": "Ashton Cox",
      "position": "Junior Technical Author",
      "salary": "$86,000",
      "start_date": "2009/01/12",
      "office": "San Francisco",
      "extn": "1562"
    },
    {
      "id": "4",
      "name": "Cedric Kelly",
      "position": "Senior Javascript Developer",
      "salary": "$433,060",
      "start_date": "2012/03/29",
      "office": "Edinburgh",
      "extn": "6224"
    },
    {
      "id": "5",
      "name": "Airi Satou",
      "position": "Accountant",
      "salary": "$162,700",
      "start_date": "2008/11/28",
      "office": "Tokyo",
      "extn": "5407"
    },
    {
      "id": "6",
      "name": "Brielle Williamson",
      "position": "Integration Specialist",
      "salary": "$372,000",
      "start_date": "2012/12/02",
      "office": "New York",
      "extn": "4804"
    },
    {
      "id": "7",
      "name": "Herrod Chandler",
      "position": "Sales Assistant",
      "salary": "$137,500",
      "start_date": "2012/08/06",
      "office": "San Francisco",
      "extn": "9608"
    },
    {
      "id": "8",
      "name": "Rhona Davidson",
      "position": "Integration Specialist",
      "salary": "$327,900",
      "start_date": "2010/10/14",
      "office": "Tokyo",
      "extn": "6200"
    },
    {
      "id": "9",
      "name": "Colleen Hurst",
      "position": "Javascript Developer",
      "salary": "$205,500",
      "start_date": "2009/09/15",
      "office": "San Francisco",
      "extn": "2360"
    },
    {
      "id": "10",
      "name": "Sonya Frost",
      "position": "Software Engineer",
      "salary": "$103,600",
      "start_date": "2008/12/13",
      "office": "Edinburgh",
      "extn": "1667"
    },
    {
      "id": "11",
      "name": "Jena Gaines",
      "position": "Office Manager",
      "salary": "$90,560",
      "start_date": "2008/12/19",
      "office": "London",
      "extn": "3814"
    },
    {
      "id": "12",
      "name": "Quinn Flynn",
      "position": "Support Lead",
      "salary": "$342,000",
      "start_date": "2013/03/03",
      "office": "Edinburgh",
      "extn": "9497"
    },
    {
      "id": "13",
      "name": "Charde Marshall",
      "position": "Regional Director",
      "salary": "$470,600",
      "start_date": "2008/10/16",
      "office": "San Francisco",
      "extn": "6741"
    },
    {
      "id": "14",
      "name": "Haley Kennedy",
      "position": "Senior Marketing Designer",
      "salary": "$313,500",
      "start_date": "2012/12/18",
      "office": "London",
      "extn": "3597"
    },
    {
      "id": "15",
      "name": "Tatyana Fitzpatrick",
      "position": "Regional Director",
      "salary": "$385,750",
      "start_date": "2010/03/17",
      "office": "London",
      "extn": "1965"
    },
    {
      "id": "16",
      "name": "Michael Silva",
      "position": "Marketing Designer",
      "salary": "$198,500",
      "start_date": "2012/11/27",
      "office": "London",
      "extn": "1581"
    },
    {
      "id": "17",
      "name": "Paul Byrd",
      "position": "Chief Financial Officer (CFO)",
      "salary": "$725,000",
      "start_date": "2010/06/09",
      "office": "New York",
      "extn": "3059"
    },
    {
      "id": "18",
      "name": "Gloria Little",
      "position": "Systems Administrator",
      "salary": "$237,500",
      "start_date": "2009/04/10",
      "office": "New York",
      "extn": "1721"
    },
    {
      "id": "19",
      "name": "Bradley Greer",
      "position": "Software Engineer",
      "salary": "$132,000",
      "start_date": "2012/10/13",
      "office": "London",
      "extn": "2558"
    },
    {
      "id": "20",
      "name": "Dai Rios",
      "position": "Personnel Lead",
      "salary": "$217,500",
      "start_date": "2012/09/26",
      "office": "Edinburgh",
      "extn": "2290"
    },
    {
      "id": "21",
      "name": "Jenette Caldwell",
      "position": "Development Lead",
      "salary": "$345,000",
      "start_date": "2011/09/03",
      "office": "New York",
      "extn": "1937"
    },
    {
      "id": "22",
      "name": "Yuri Berry",
      "position": "Chief Marketing Officer (CMO)",
      "salary": "$675,000",
      "start_date": "2009/06/25",
      "office": "New York",
      "extn": "6154"
    },
    {
      "id": "23",
      "name": "Caesar Vance",
      "position": "Pre-Sales Support",
      "salary": "$106,450",
      "start_date": "2011/12/12",
      "office": "New York",
      "extn": "8330"
    },
    {
      "id": "24",
      "name": "Doris Wilder",
      "position": "Sales Assistant",
      "salary": "$85,600",
      "start_date": "2010/09/20",
      "office": "Sydney",
      "extn": "3023"
    },
    {
      "id": "25",
      "name": "Angelica Ramos",
      "position": "Chief Executive Officer (CEO)",
      "salary": "$1,200,000",
      "start_date": "2009/10/09",
      "office": "London",
      "extn": "5797"
    },
    {
      "id": "26",
      "name": "Gavin Joyce",
      "position": "Developer",
      "salary": "$92,575",
      "start_date": "2010/12/22",
      "office": "Edinburgh",
      "extn": "8822"
    },
    {
      "id": "27",
      "name": "Jennifer Chang",
      "position": "Regional Director",
      "salary": "$357,650",
      "start_date": "2010/11/14",
      "office": "Singapore",
      "extn": "9239"
    },
    {
      "id": "28",
      "name": "Brenden Wagner",
      "position": "Software Engineer",
      "salary": "$206,850",
      "start_date": "2011/06/07",
      "office": "San Francisco",
      "extn": "1314"
    },
    {
      "id": "29",
      "name": "Fiona Green",
      "position": "Chief Operating Officer (COO)",
      "salary": "$850,000",
      "start_date": "2010/03/11",
      "office": "San Francisco",
      "extn": "2947"
    },
    {
      "id": "30",
      "name": "Shou Itou",
      "position": "Regional Marketing",
      "salary": "$163,000",
      "start_date": "2011/08/14",
      "office": "Tokyo",
      "extn": "8899"
    },
    {
      "id": "31",
      "name": "Michelle House",
      "position": "Integration Specialist",
      "salary": "$95,400",
      "start_date": "2011/06/02",
      "office": "Sydney",
      "extn": "2769"
    },
    {
      "id": "32",
      "name": "Suki Burks",
      "position": "Developer",
      "salary": "$114,500",
      "start_date": "2009/10/22",
      "office": "London",
      "extn": "6832"
    },
    {
      "id": "33",
      "name": "Prescott Bartlett",
      "position": "Technical Author",
      "salary": "$145,000",
      "start_date": "2011/05/07",
      "office": "London",
      "extn": "3606"
    },
    {
      "id": "34",
      "name": "Gavin Cortez",
      "position": "Team Leader",
      "salary": "$235,500",
      "start_date": "2008/10/26",
      "office": "San Francisco",
      "extn": "2860"
    },
    {
      "id": "35",
      "name": "Martena Mccray",
      "position": "Post-Sales support",
      "salary": "$324,050",
      "start_date": "2011/03/09",
      "office": "Edinburgh",
      "extn": "8240"
    },
    {
      "id": "36",
      "name": "Unity Butler",
      "position": "Marketing Designer",
      "salary": "$85,675",
      "start_date": "2009/12/09",
      "office": "San Francisco",
      "extn": "5384"
    },
    {
      "id": "37",
      "name": "Howard Hatfield",
      "position": "Office Manager",
      "salary": "$164,500",
      "start_date": "2008/12/16",
      "office": "San Francisco",
      "extn": "7031"
    },
    {
      "id": "38",
      "name": "Hope Fuentes",
      "position": "Secretary",
      "salary": "$109,850",
      "start_date": "2010/02/12",
      "office": "San Francisco",
      "extn": "6318"
    },
    {
      "id": "39",
      "name": "Vivian Harrell",
      "position": "Financial Controller",
      "salary": "$452,500",
      "start_date": "2009/02/14",
      "office": "San Francisco",
      "extn": "9422"
    },
    {
      "id": "40",
      "name": "Timothy Mooney",
      "position": "Office Manager",
      "salary": "$136,200",
      "start_date": "2008/12/11",
      "office": "London",
      "extn": "7580"
    },
    {
      "id": "41",
      "name": "Jackson Bradshaw",
      "position": "Director",
      "salary": "$645,750",
      "start_date": "2008/09/26",
      "office": "New York",
      "extn": "1042"
    },
    {
      "id": "42",
      "name": "Olivia Liang",
      "position": "Support Engineer",
      "salary": "$234,500",
      "start_date": "2011/02/03",
      "office": "Singapore",
      "extn": "2120"
    },
    {
      "id": "43",
      "name": "Bruno Nash",
      "position": "Software Engineer",
      "salary": "$163,500",
      "start_date": "2011/05/03",
      "office": "London",
      "extn": "6222"
    },
    {
      "id": "44",
      "name": "Sakura Yamamoto",
      "position": "Support Engineer",
      "salary": "$139,575",
      "start_date": "2009/08/19",
      "office": "Tokyo",
      "extn": "9383"
    },
    {
      "id": "45",
      "name": "Thor Walton",
      "position": "Developer",
      "salary": "$98,540",
      "start_date": "2013/08/11",
      "office": "New York",
      "extn": "8327"
    },
    {
      "id": "46",
      "name": "Finn Camacho",
      "position": "Support Engineer",
      "salary": "$87,500",
      "start_date": "2009/07/07",
      "office": "San Francisco",
      "extn": "2927"
    },
    {
      "id": "47",
      "name": "Serge Baldwin",
      "position": "Data Coordinator",
      "salary": "$138,575",
      "start_date": "2012/04/09",
      "office": "Singapore",
      "extn": "8352"
    },
    {
      "id": "48",
      "name": "Zenaida Frank",
      "position": "Software Engineer",
      "salary": "$125,250",
      "start_date": "2010/01/04",
      "office": "New York",
      "extn": "7439"
    },
    {
      "id": "49",
      "name": "Zorita Serrano",
      "position": "Software Engineer",
      "salary": "$115,000",
      "start_date": "2012/06/01",
      "office": "San Francisco",
      "extn": "4389"
    },
    {
      "id": "50",
      "name": "Jennifer Acosta",
      "position": "Junior Javascript Developer",
      "salary": "$75,650",
      "start_date": "2013/02/01",
      "office": "Edinburgh",
      "extn": "3431"
    },
    {
      "id": "51",
      "name": "Cara Stevens",
      "position": "Sales Assistant",
      "salary": "$145,600",
      "start_date": "2011/12/06",
      "office": "New York",
      "extn": "3990"
    },
    {
      "id": "52",
      "name": "Hermione Butler",
      "position": "Regional Director",
      "salary": "$356,250",
      "start_date": "2011/03/21",
      "office": "London",
      "extn": "1016"
    },
    {
      "id": "53",
      "name": "Lael Greer",
      "position": "Systems Administrator",
      "salary": "$103,500",
      "start_date": "2009/02/27",
      "office": "London",
      "extn": "6733"
    },
    {
      "id": "54",
      "name": "Jonas Alexander",
      "position": "Developer",
      "salary": "$86,500",
      "start_date": "2010/07/14",
      "office": "San Francisco",
      "extn": "8196"
    },
    {
      "id": "55",
      "name": "Shad Decker",
      "position": "Regional Director",
      "salary": "$183,000",
      "start_date": "2008/11/13",
      "office": "Edinburgh",
      "extn": "6373"
    },
    {
      "id": "56",
      "name": "Michael Bruce",
      "position": "Javascript Developer",
      "salary": "$183,000",
      "start_date": "2011/06/27",
      "office": "Singapore",
      "extn": "5384"
    },
    {
      "id": "57",
      "name": "Donna Snider",
      "position": "Customer Support",
      "salary": "$112,000",
      "start_date": "2011/01/25",
      "office": "New York",
      "extn": "4226"
    }
  ]
})





@app.route('/', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return flask.redirect(flask.url_for("main_form"))

    if flask.request.method == 'POST':
        username = flask.request.form.get('username')
        password = flask.request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user:
            if user.check_password(password=password):
                user_db_mgr.create_user_db(username)
                login_user(user)
                return flask.redirect(flask.url_for("main_form"))

        flask.flash('Invalid username/password combination')
        return flask.redirect(flask.url_for("login_page"))

    return flask.render_template('login.html', form=LoginForm())


if __name__ == "__main__":
    app.run(host='0.0.0.0')
