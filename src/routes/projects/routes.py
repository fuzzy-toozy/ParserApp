import flask

from flask_login import login_required, current_user
from flask import Blueprint


from database.models import Project
from common.forms import ProjectForm
from database.users import session_scope
from routes.shared import bc_generator, ENTS


projects = Blueprint("projects", __name__)


@projects.route('/main', methods=['GET'])
@login_required
def main_form():
    bc_generator.init_user(current_user.username)
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username)

    with session_scope(current_user.username) as session:
        user_projects = session.query(Project).all()

        if user_projects and len(user_projects) == 0:
            user_projects = None
        ctx = {"current_user": current_user, "projects": user_projects, "bc_data": bc_data}
        return flask.render_template("project/projects.html", **ctx)


@projects.route("/create_project", methods=['GET', 'POST'])
@login_required
def create_project():
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, None, ENTS.CREATE_PROJECT)
    if flask.request.method == "GET":
        return flask.render_template("project/create_project.html", current_user=current_user.username, form=ProjectForm(), bc_data=bc_data)
    else:
        project_name = flask.request.form.get("project_name")
        with session_scope(current_user.username) as session:
            session.add(Project(name=project_name))
        return flask.redirect(flask.url_for("projects.main_form"))


@projects.route("/project_settings/<project_id>", methods=['GET', 'POST'])
@login_required
def project_settings(project_id):
    if flask.request.method == "GET":
        bc_data = bc_generator.get_breadcrumbs_data(current_user.username, None, ENTS.EDIT_PROJECT)
        with session_scope(current_user.username) as session:
            current_project = session.query(Project).filter(Project.id == project_id).first()
            project_name = current_project.name if current_project else ""
        return flask.render_template("project/project_settings.html", current_user=current_user,
                                     form=ProjectForm(), project_id=project_id, bc_data=bc_data, project_name=project_name)
    else:
        with session_scope(current_user.username) as session:
            current_proj = session.query(Project).filter(Project.id == project_id).first()
            if current_proj:
                current_proj.name = flask.request.form.get("project_name")
            return flask.redirect(flask.url_for("projects.main_form"))


@projects.route("/project_view/<project_id>", methods=['GET'])
@login_required
def project_view(project_id):
    bc_data = bc_generator.get_breadcrumbs_data(current_user.username, project_id)
    ctx = {"current_user": current_user,
           "project_id": project_id,
           "bc_data": bc_data}
    return flask.render_template("project/project_view.html", **ctx)


@projects.route("/delete_project", methods=['POST'])
@login_required
def delete_project():
    request_js = flask.request.get_json()

    with session_scope(current_user.username) as session:
        session.query(Project).filter(Project.id == int(request_js['name'])).delete()

    return flask.redirect(flask.url_for("projects.main_form"))
