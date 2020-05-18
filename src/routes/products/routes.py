import flask
import json

from flask_login import login_required, current_user
from flask import Blueprint


from database.models import Product, ProductOption, MonitoredProduct, MonitoredOption
from database.users import session_scope
from routes.shared import bc_generator, ENTS


products = Blueprint("products", __name__)


@products.route("/products_view/<project_id>", methods=['GET'])
@login_required
def products_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.PRODUCTS)
    if flask.request.method == 'GET':
        with session_scope(current_user.username) as session:
            current_products = session.query(Product).filter(Product.project_id == int(project_id)).all()
            return flask.render_template("product/products_view.html",
                                         current_user=current_user,
                                         project_id=project_id,
                                         products=current_products,
                                         bc_data=bc_data)


@products.route("/edit_product/<project_id>/<product_id>", methods=['GET'])
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
                                 redirect_url=flask.url_for("products.products_view", project_id=project_id),
                                 current_user=current_user,
                                 product_options=current_product_opts,
                                 product_name=current_product_name,
                                 project_id=project_id,
                                 product_id=product_id,
                                 bc_data=bc_data)


@products.route("/save_product", methods=['POST'])
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


@products.route("/delete_product", methods=['POST'])
@login_required
def delete_product():
    request_json = flask.request.get_json()
    product_id = int(request_json['product_id'])
    project_id = int(request_json['project_id'])

    with session_scope(current_user.username) as session:
        session.query(Product).filter(Product.id == product_id).delete()

    return flask.redirect(flask.url_for("products.products_view", project_id=project_id))
