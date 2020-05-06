import json
import flask

from flask import Flask
from sqlalchemy import MetaData, and_
import sqlalchemy
from flask_login import LoginManager, login_required, logout_user, current_user, login_user
from flask_session import Session

from datetime import timedelta

from common import parsing
from database.users import create_admin, user_db_mgr, session_scope
from database.models import *
from common.forms import LoginForm
from common.settings import SECRET_KEY

from common.scanning import ScanningResult, ScanProcessor

from routes.sellers.routes import sellers
from routes.projects.routes import projects
from routes.products.routes import products
from routes.parsers.routes import parsers
from routes.monitorings.routes import monitorings

login_manager = LoginManager()


class ServerApp:
    def __init__(self, flask_login_mgr):
        self.root_dir = "/home/fuzzy/shit/gledos/gachi_parser/"
        self.flask_app = Flask(__name__, root_path=self.root_dir)
        self.login_manager = flask_login_mgr
        self.db = None
        self.session = Session()
        self.scan_processor = ScanProcessor()
        self.db_engine = None

    def init(self):
        self.flask_app.register_blueprint(sellers)
        self.flask_app.register_blueprint(projects)
        self.flask_app.register_blueprint(products)
        self.flask_app.register_blueprint(parsers)
        self.flask_app.register_blueprint(monitorings)

        self.flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.flask_app.config["SECRET_KEY"] = SECRET_KEY
        self.flask_app.secret_key = SECRET_KEY
        self.flask_app.config["SESSION_TYPE"] = "sqlalchemy"
        self.flask_app.config["SESSION_SQLALCHEMY"] = flask_db

        self.session.init_app(self.flask_app)
        self.login_manager.init_app(self.flask_app)
        self.init_db()
        self.run_scan_workers()

    def create_app(self):
        self.init()
        return self.flask_app

    def run(self):
        self.flask_app.run()

    def finish(self):
        self.scan_processor.stop_scan_workers()

    def run_scan_workers(self):
        if not self.scan_processor.is_initialised():
            with self.flask_app.app_context():
                all_users = User.query.all()
                users_set = set()
                for user in all_users:
                    users_set.add(user.username)
                self.scan_processor.init_users(users_set)
            self.scan_processor.run_scan()

    def init_db(self):
        self.flask_app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///%s/db_data/%s.db" % (self.root_dir, "main_app.db")
        self.flask_app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"
        flask_db.init_app(self.flask_app)

        with self.flask_app.app_context():
            flask_db.create_all()
            create_admin()

    def add_scan_object(self, project_id, monitoring_id, user):
        self.scan_processor.add_scan_object(project_id, monitoring_id, user)

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
