import sqlalchemy
from datetime import datetime as dt

from .database import flask_db, DB_ROOT
from .models import User, Base
from werkzeug.security import generate_password_hash
from contextlib import contextmanager


def create_admin():
    exists = flask_db.session.query(flask_db.exists().where(User.username == "Admin")).scalar()
    if not exists:
        admin_user = User(username="Admin", password=generate_password_hash('Admin1488'), created=dt.now(), admin=True)
        flask_db.session.add(admin_user)

        try:
            flask_db.session.commit()
        except sqlalchemy.exc.SQLAlchemyError as ex:
            print("Failed adding admin")
            return False
        print("Admin created successfully")

    return True


class UserDbManager:
    def __init__(self, db_root):
        self.db_root = db_root
        self.db_engine = None
        self.session_maker = None

    def create_user_db(self, username):
        self.db_engine = sqlalchemy.create_engine("sqlite:///%s/%s.db" % (self.db_root, username))
        Base.metadata.create_all(self.db_engine)

    def get_user_db_session(self, username):
        if self.db_engine is None:
            self.db_engine = sqlalchemy.create_engine("sqlite:///%s/%s.db" % (self.db_root, username))
        if self.session_maker is None:
            self.session_maker = sqlalchemy.orm.sessionmaker(bind=self.db_engine)
        return self.session_maker()


user_db_mgr = UserDbManager(DB_ROOT)


@contextmanager
def session_scope(username, expunge=False):
    session = user_db_mgr.get_user_db_session(username)
    try:
        yield session
        if expunge:
            session.expunge_all()
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
