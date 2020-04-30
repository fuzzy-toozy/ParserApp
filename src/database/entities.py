import sqlalchemy
from .models import Project


def create_project(session, project_name):
    exists = session.query(sqlalchemy.exists().where(Project.name == project_name)).scalar()
    if not exists:
        new_project = Project(name=project_name)
        session.add(new_project)
        try:
            session.commit()
        except sqlalchemy.exc.SQLAlchemyError as ex:
            session.rollback()
            return False
        session.close()
        return True

    return False
