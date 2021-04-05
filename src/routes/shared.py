import flask

from database.models import *
from database.users import session_scope
from sqlalchemy import and_


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

    TEST_PARSER = 0x400


class BreadcrumbsGenerator:
    def __init__(self):
        self.api_names = {
                            ENTS.PROJECTS: ("Projects", "projects.main_form"),
                            ENTS.MONITORINGS: ("Monitorings", "monitorings.monitorings_view"),
                            ENTS.PARSERS: ("Parsers", "parsers.parsers_view"),
                            ENTS.SELLERS: ("Sellers", "sellers.sellers_view"),
                            ENTS.PRODUCTS: ("Products", "products.products_view"),
                            ENTS.PROJECT: ("Project", "projects.project_view"),
                            ENTS.MONITORING: ("monitoring_id", "monitorings.monitoring_view_flat"),
                            ENTS.REPORT: ("entity_id", "reports.report_view"),
                            ENTS.REPORTS: ("Reports", "reports.reports_view"),
                            ENTS.EDIT_MONITORING: ("Edit monitoring", None),
                            ENTS.EDIT_SELLER: ("Edit seller", None),
                            ENTS.EDIT_PRODUCT: ("Edit product", None),
                            ENTS.EDIT_PARSER: ("Edit parser", "parsers.edit_parser"),
                            ENTS.EDIT_PROJECT: ("Edit project", None),
                            ENTS.EDIT_MONITORING_OBJECT: ("Edit monitoring object", None),
                            ENTS.EDIT_REPORT: ("Edit report", None),
                            ENTS.CREATE_MONITORING: ("Create monitoring", None),
                            ENTS.CREATE_SELLER: ("Create seller", None),
                            ENTS.CREATE_PRODUCT: ("Create product", None),
                            ENTS.CREATE_PROJECT: ("Create project", None),
                            ENTS.CREATE_PARSER: ("Create parser", None),
                            ENTS.CREATE_MONITORING_OBJECT: ("Create monitoring object", None),
                            ENTS.CREATE_REPORT: ("Create report", None),
                            ENTS.TEST_PARSER: ("Test parser", None)
        }

    def init_user(self, user_name):
        self.user_name = user_name

    def get_breadcrumbs_data(self, user_name, project_id=None, last_id=None, views_list=None, ent_model=None, ent_db_id=None, ent_ep_id=None):
        bc_result = []

        pr_name, pr_endp = self.api_names[ENTS.PROJECTS]
        bc_result.append((pr_name, flask.url_for(pr_endp)))

        if last_id == ENTS.PROJECTS:
            return bc_result

        with session_scope() as session:

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
                template_data = {"project_id": project_id,
                                  ent_name_id: ent_db_id }

                bc_result.append((current_entity.name, flask.url_for(entity_endp, **template_data)))

            if last_id:
                bc_result.append((self.api_names[last_id][0], "#"))

            return bc_result


bc_generator = BreadcrumbsGenerator()
