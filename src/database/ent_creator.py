from .models import Project


def create_project(session, name):
    try:
        session.add(Project(name=name))
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
