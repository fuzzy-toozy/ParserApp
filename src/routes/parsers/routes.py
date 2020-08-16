import flask
import json

from flask_login import login_required, current_user
from flask import Blueprint
from flask_wtf import FlaskForm

from sqlalchemy import and_

import common.parsing as parsing

from database.models import Parser
from database.users import session_scope
from routes.shared import bc_generator, ENTS
from common.settings import PARSERS_DIR


parsers = Blueprint("parsers", __name__)


def validate_parser(parser_file, parser_name, parsers_dir):
    response_dict = {}
    validation_res = False
    try:
        parser_code = parser_file.read()
        parser_code = parser_code.decode("utf-8")
    except Exception as ex:
        parser_code = None
        response_dict["result"] = "ERROR"
        response_dict["message"] = str(ex)

    if parser_code:
        parser_module, err_msg, parser_code, _ = parsing.make_parser_module(parser_code, parser_name, parsers_dir)
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


@parsers.route("/parsers_view/<project_id>", methods=['GET'])
@login_required
def parsers_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id, ENTS.PARSERS)
    with session_scope(current_user.username, True) as session:
        current_sellers = session.query(Parser).filter(Parser.project_id == int(project_id)).all()

    new_entity_url = flask.url_for('parsers.edit_parser', project_id=project_id, entity_id='new_entity')
    delete_entity_url = flask.url_for('parsers.delete_parser')
    entity_view_url = flask.url_for('parsers.parsers_view', project_id=project_id)
    edit_entity = 'parsers.edit_parser'

    return flask.render_template("parser/parsers_view.html",
                                 current_user=current_user,
                                 project_id=project_id,
                                 entities=current_sellers,
                                 common_name="parser",
                                 new_entity_url=new_entity_url,
                                 delete_entity_url =delete_entity_url,
                                 entity_view_url=entity_view_url,
                                 edit_entity=edit_entity,
                                 bc_data=bc_data,
                                 create_ent_txt="Create Parser")


@parsers.route("/edit_parser/<project_id>/<entity_id>", methods=['GET', 'POST'])
@login_required
def edit_parser(project_id, entity_id):
    if flask.request.method == 'GET':
        entity_view_url = flask.url_for('parsers.parsers_view', project_id=project_id)
        save_entity_url = flask.url_for('parsers.edit_parser', project_id=project_id, entity_id=entity_id)
        test_parser_url = flask.url_for('parsers.test_parser_view', project_id=project_id, parser_id=entity_id)

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
                                     current_user=current_user,
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


@parsers.route("/delete_parser", methods=['POST'])
@login_required
def delete_parser():
    request_js = flask.request.get_json()
    print(request_js)
    parser_id = request_js['id']
    project_id = request_js['project_id']
    with session_scope(current_user.username) as session:
        session.query(Parser).filter(Parser.id == parser_id).delete()
    return flask.redirect(flask.url_for("parsers.parsers_view", project_id=project_id))


@parsers.route("/test_parser/<project_id>/<parser_id>", methods=['POST'])
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

    return flask.render_template("parser/test_parser.html", current_user=current_user,
                                 label_message=label_message,
                                 parser_exec_ok=parser_exec_ok,
                                 parser_result=parser_result,
                                 current_parser=current_parser,
                                 parser_code=parser_code,
                                 project_id=project_id,
                                 back_url=flask.url_for("parsers.test_parser_view", project_id=project_id, parser_id=parser_id))


@parsers.route("/test_parser_view/<project_id>/<parser_id>", methods=['GET'])
@login_required
def test_parser_view(project_id, parser_id):
    with session_scope(current_user.username, True) as session:
        current_parser = session.query(Parser).filter(and_(Parser.id == parser_id, Parser.project_id == project_id)).first()
    if current_parser and current_parser.code:
        parser_code = current_parser.code
    else:
        parser_code = None
    form = FlaskForm()
    submit_url = flask.url_for("parsers.test_parser", project_id=project_id, parser_id=parser_id)
    return flask.render_template("parser/test_parser_view.html", current_user=current_user,
                                 current_parser=current_parser,
                                 form=form,
                                 parser_code=parser_code,
                                 project_id=project_id,
                                 submit_url=submit_url,
                                 back_url=flask.url_for("parsers.edit_parser", project_id=project_id, entity_id=parser_id))
