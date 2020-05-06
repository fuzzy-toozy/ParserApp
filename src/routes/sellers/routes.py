import flask

from flask_login import login_required, current_user
from flask import Blueprint


from database.models import Seller
from common.forms import SellerForm
from database.users import session_scope
from routes.shared import bc_generator, ENTS


sellers = Blueprint("sellers", __name__)


@sellers.route("/edit_seller/<project_id>/<entity_id>", methods=['GET', 'POST'])
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
                                     entity_view_url=flask.url_for('sellers.sellers_view', project_id=project_id),
                                     save_entity_url=flask.url_for('sellers.edit_seller', project_id=project_id,
                                                                   entity_id=entity_id))
    else:
        with session_scope(current_user.username) as session:
            if entity_id == 'new_entity':
                session.add(Seller(name=flask.request.form.get('name'), project_id=int(project_id)))
            else:
                current_seller = session.query(Seller).filter(Seller.id == entity_id).first()
                current_seller.name = flask.request.form.get('name')

        return flask.redirect(flask.url_for("sellers.sellers_view",
                                            project_id=project_id))


@sellers.route("/sellers_view/<project_id>", methods=['GET'])
@login_required
def sellers_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.SELLERS)
    with session_scope(current_user.username, True) as session:
        current_sellers = session.query(Seller).filter(Seller.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('sellers.edit_seller', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('sellers.delete_seller')
    entity_view_url = flask.url_for('sellers.sellers_view', project_id=project_id)
    edit_entity = 'sellers.edit_seller'

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


@sellers.route("/delete_seller", methods=['POST'])
@login_required
def delete_seller():
    request_js = flask.request.get_json()
    print(request_js)
    seller_id = request_js['id']
    project_id = request_js['project_id']
    with session_scope(current_user.username) as session:
        session.query(Seller).filter(Seller.id == seller_id).delete()

    return flask.redirect(flask.url_for("sellers.sellers_view", project_id=project_id))
