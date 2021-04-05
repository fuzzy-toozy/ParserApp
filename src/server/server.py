import json
import flask
import logging
#import uwsgi

from functools import partial
from flask import Flask
from sqlalchemy import MetaData, and_
import sqlalchemy
from flask_login import LoginManager, login_required, logout_user, current_user, login_user
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError

from datetime import timedelta
from common import parsing
from database.users import create_admin, user_db_mgr, session_scope
from database.models import *
from common.forms import LoginForm
from common.settings import SECRET_KEY

from common.scanning import ScanProcessor
from common.reports import ReportSender

from routes.sellers.routes import sellers
from routes.projects.routes import projects
from routes.products.routes import products
from routes.parsers.routes import parsers
from routes.monitorings.routes import monitorings
from routes.reports.routes import reports
from routes.settings.routes import settings

from common.scanning import ScanningResult
from common.settings import get_config

login_manager = LoginManager()
log = logging.getLogger(__name__)


#def uwsgi_at_exit(server_app, *args):
#    server_app.finish()


class ServerApp:
    def __init__(self, flask_login_mgr):
        #self.uwsgi_at_exit = partial(uwsgi_at_exit, self)
        #uwsgi.atexit = self.uwsgi_at_exit
        self.conf = get_config()
        self.server = self.conf["ServerRemote"]
        self.port = str(self.conf["Port"])
        self.schema = self.conf["Schema"]
        self.root_dir = self.conf["RootDir"]
        self.flask_app = Flask(__name__, root_path=self.root_dir)
        self.login_manager = flask_login_mgr

        self.session = Session()
        self.scan_processor = ScanProcessor()
        self.report_sender = ReportSender(self.flask_app.jinja_env)
        self.csrf_protect = CSRFProtect()

        self.db = None
        self.db_engine = None

    def init(self):
        self.flask_app.register_blueprint(sellers)
        self.flask_app.register_blueprint(projects)
        self.flask_app.register_blueprint(products)
        self.flask_app.register_blueprint(parsers)
        self.flask_app.register_blueprint(monitorings)
        self.flask_app.register_blueprint(reports)
        self.flask_app.register_blueprint(settings)

        self.flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.flask_app.config["SECRET_KEY"] = SECRET_KEY
        self.flask_app.secret_key = SECRET_KEY
        self.flask_app.config["SESSION_TYPE"] = "sqlalchemy"
        self.flask_app.config["SESSION_SQLALCHEMY"] = flask_db

        self.csrf_protect.init_app(self.flask_app)
        self.session.init_app(self.flask_app)
        self.login_manager.init_app(self.flask_app)
        self.init_db()
        self.run_workers()

    def get_root_dir(self):
        return self.root_dir

    def create_app(self):
        self.init()
        return self.flask_app

    def get_server_addr(self):
        return self.schema, self.server, self.port

    def run(self):
        self.flask_app.run()

    def finish(self):
        log.info("Stopping workers")
        self.report_sender.stop()
        self.scan_processor.stop_scan_workers()

    def run_workers(self):
        if not self.scan_processor.is_initialised():
            with self.flask_app.app_context():
                all_users = User.query.all()
                users_set = set()
                for user in all_users:
                    users_set.add(user.id)
                self.scan_processor.init_users(users_set)
            self.scan_processor.run_scan()

        self.report_sender.start()

    def init_db(self):
        self.flask_app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///%s/db_data/%s.db" % (self.root_dir, "main_app.db")
        self.flask_app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"
        flask_db.init_app(self.flask_app)

        with self.flask_app.app_context():
            flask_db.create_all()
            create_admin()
        user_db_mgr.create_user_db()

    def add_scan_object(self, project_id, monitoring_id, user_id):
        self.scan_processor.add_scan_object(project_id, monitoring_id, user_id)

    def get_scan_stats(self, user):
        return self.scan_processor.get_stats(user)

    def create_db_tables(self, user):
        self.db_engine = sqlalchemy.create_engine("sqlite:///%s/db_data/%s.db" % (self.root_dir, user))

        metadata = MetaData()
        try:
            metadata.create_all(self.db_engine)
            print("Tables created")
        except Exception as e:
            print("Error occurred during Table creation!")
            print(e)


main_app = ServerApp(login_manager)
app = main_app.create_app()

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return e.description, 400


@app.before_request
def set_session_timeout():
    flask.session.permanent = True
    app.permanent_session_lifetime = timedelta(days=1000)


@app.route("/check_ajax", methods=['POST'])
def check():
    request_json = flask.request.get_json()

    main_app.create_db_tables("faggot")

    query = User.query.filter(User.username == "Admin").first()

    return "<p> %s, %s, %s</p>" % (query.username, query.created, query.admin)


@login_manager.user_loader
def load_user(user_id):
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

@app.route("/scan_stats")
@login_required
def show_scan_stats():
    view_data = main_app.get_scan_stats(current_user.get_id())
    return flask.render_template("scan_stats.html", current_user=current_user,
                                 view_data=view_data,
                                 scan_state=view_data["state"])


@app.route("/show_scan_res/<project_id>/<entity_id>", methods=['GET'])
@login_required
def scan_res(project_id, entity_id):
    with session_scope() as session:
        scan_results = session.query(BaseScanResult, MonitoredProduct, Product, Seller).filter(and_(BaseScanResult.project_id == project_id,
                                                                                                    BaseScanResult.monitoring_id == entity_id,
                                                                                                    MonitoredProduct.id == BaseScanResult.monitored_product_id,
                                                                                                    MonitoredProduct.monitoring_id == entity_id,
                                                                                                    MonitoredProduct.project_id == project_id,
                                                                                                    Product.id == MonitoredProduct.product_id,
                                                                                                    Seller.id == MonitoredProduct.seller_id)).all()
        scan_results_js = {}
        for result, mon_product, product, seller in scan_results:
            current_result = scan_results_js.get(product.name)
            if current_result is None:
                current_result = {}
                scan_results_js[product.name] = current_result

            current_seller_result = current_result.get(seller.name)
            if current_seller_result is None:
                current_seller_result = {}
                current_result[seller.name] = current_seller_result

            current_seller_result["rescode"] = result.result_code
            current_seller_result["result"] = result.scan_result
            current_seller_result["error"] = result.scan_error
            options_result = []
            current_seller_result["options"] = options_result

            scan_options_results = session.query(OptionScanResult, MonitoredOption, ProductOption).filter(
                and_(OptionScanResult.project_id == project_id,
                     OptionScanResult.monitoring_id == entity_id,
                     MonitoredOption.monitored_product_id == mon_product.id,
                     MonitoredOption.id == OptionScanResult.option_id,
                     MonitoredOption.monitoring_id == entity_id,
                     MonitoredOption.project_id == project_id)).outerjoin(ProductOption,
                                                                          ProductOption.id == MonitoredOption.option_id).all()

            for option_result, mon_option, product_option in scan_options_results:
                current_option = {}
                current_option["rescode"] = option_result.result_code
                current_option["result"] = option_result.scan_result
                current_option["error"] = option_result.scan_error
                current_option["name"] = product_option.name
                options_result.append(current_option)

        return flask.jsonify(scan_results_js)


@app.route("/force_scan/<project_id>/<entity_id>", methods=['GET'])
@login_required
def force_scan(project_id, entity_id):
    with session_scope() as session:
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

@app.route("/force_scan_test/<project_id>/<entity_id>", methods=['POST'])
@login_required
def force_scan_test(project_id, entity_id):
    user_id = int(current_user.get_id())
    main_app.add_scan_object(project_id, entity_id, user_id)
    return flask.jsonify(main_app.get_scan_stats(user_id))

@app.route("/scan_statss", methods=['GET'])
@login_required
def scan_statss():
    return flask.jsonify(main_app.get_scan_stats(current_user.get_id()))


@app.route('/', methods=['GET', 'POST'])
def login_page():

    if current_user.is_authenticated:
        return flask.redirect(flask.url_for("projects.main_form"))

    if flask.request.method == 'POST':
        print("AMIPOST?")
        print(flask.request.form)
        username = flask.request.form.get('username')
        password = flask.request.form.get('password')

        user = User.query.filter_by(username=username).first()
        usrs = User.query.all()
        print(usrs)
        if user:
            if user.check_password(password=password):
                login_user(user)
                return flask.redirect(flask.url_for("projects.main_form"))

        return 'Invalid username/password combination'

    return flask.render_template('login.html', form=LoginForm())


if __name__ == "__main__":
    app.run(host='0.0.0.0')
