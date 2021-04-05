import os

from common.settings import get_root_dir
from flask_sqlalchemy import SQLAlchemy
flask_db = SQLAlchemy()

DB_ROOT = os.path.join(get_root_dir(), "db_data")
