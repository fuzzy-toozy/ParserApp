from .database import flask_db

from sqlalchemy.types import *
from sqlalchemy_utcdatetime import UTCDateTime
from sqlalchemy import Column, ForeignKey, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import Engine
from sqlalchemy import event
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

Base = declarative_base()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Project(Base):
    __tablename__ = "Projects"

    id = Column(Integer, primary_key=True)

    name = Column(String(64), index=True, unique=True, nullable=False)

    products = Column(Text(), index=False, unique=False, nullable=True)

    sellers = Column(Text(), index=False, unique=False, nullable=True)

    monitorings = Column(Text(), index=False, unique=False, nullable=True)

    parsers = Column(Text(), index=False, unique=False, nullable=True)


class User(UserMixin, flask_db.Model):

    __tablename__ = 'users'

    id = flask_db.Column(flask_db.Integer, primary_key=True)

    username = flask_db.Column(flask_db.String(64), index=True, unique=True, nullable=False)

    password = flask_db.Column(flask_db.String(200), primary_key=False, unique=False, nullable=False)

    created = flask_db.Column(flask_db.DateTime, index=False, unique=False, nullable=False)

    admin = flask_db.Column(flask_db.Boolean, index=False, unique=False, nullable=False)

    avatar = flask_db.Column(flask_db.BLOB, nullable=True)

    def set_password(self, password):
        self.password = generate_password_hash(password, method='sha256')

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)


class UserEmail(Base):
    __tablename__ = 'users_email'

    id = flask_db.Column(flask_db.Integer, primary_key=True)
    user_id = flask_db.Column(flask_db.Integer, primary_key=False, unique=False, index=True)
    email = flask_db.Column(flask_db.String(), index=True, nullable=False, unique=True)


class SmtpSettings(Base):
    __tablename__ = 'Smtp_settings'

    id = flask_db.Column(flask_db.Integer, primary_key=True)
    user_id = flask_db.Column(flask_db.Integer, primary_key=False, unique=False, index=True)
    port = flask_db.Column(flask_db.Integer, primary_key=False, unique=False, nullable=True)
    address = flask_db.Column(flask_db.String(), index=False, unique=False, nullable=True)
    mailbox = flask_db.Column(flask_db.String(), index=False, unique=False, nullable=True)
    password = flask_db.Column(flask_db.String(), index=False, unique=False, nullable=True)


class Parser(Base):
    __tablename__ = "Parsers"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id = Column(Integer, primary_key=True)

    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False)

    name = Column(String(64), index=True, unique=False, nullable=False)

    code = Column(Text(), index=False, unique=False, nullable=True)


class Product(Base):
    __tablename__ = "Products"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(128), index=True, unique=False, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False)


class ProductOption(Base):
    __tablename__ = "ProductOptions"
    __table_args__ = (UniqueConstraint("product_id", "name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(128), index=True, unique=False, nullable=False)
    product_id = Column(Integer, ForeignKey(Product.id, ondelete="CASCADE"), index=True, primary_key=False)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False)


class Seller(Base):
    __tablename__ = "Sellers"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id = Column(Integer, primary_key=True)

    name = Column(String(128), index=True, unique=False, nullable=False)

    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False)


class Monitoring(Base):
    __tablename__ = "Monitorings"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id = Column(Integer, primary_key=True)

    name = Column(String(64), index=True, unique=False, nullable=False)

    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False)

    seller_self_id = Column(Integer, ForeignKey(Seller.id, ondelete="SET NULL"), index=True, primary_key=False, nullable=True)
    update_interval = Column(Integer, index=False, primary_key=False, nullable=True)
    request_interval = Column(Integer, index=False, primary_key=False, nullable=True)
    enabled = Column(Boolean, unique=False, default=True)


class MonitoringSeller(Base):
    __tablename__ = "MonitoringSellers"
    __table_args__ = (UniqueConstraint("seller_id", "monitoring_id"),)

    id = Column(Integer, index=False, primary_key=True, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, primary_key=False, nullable=False)
    seller_id = Column(Integer, ForeignKey(Seller.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)


class MonitoringProduct(Base):
    __tablename__ = "MonitoringProducts"
    __table_args__ = (UniqueConstraint("product_id", "monitoring_id"),)

    id = Column(Integer, index=False, primary_key=True, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, primary_key=False, nullable=False)
    product_id = Column(Integer, ForeignKey(Product.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)


class MonitoredProduct(Base):
    __tablename__ = "Monitored_products"
    __table_args__ = (UniqueConstraint("product_id", "seller_id", "monitoring_id"),)

    id = Column(Integer, primary_key=True)

    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False)

    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False)

    url = Column(Text(), index=False, unique=False, nullable=True)

    parser_id = Column(Integer, ForeignKey(Parser.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=True)

    parser_parameter = Column(Text(), index=False, unique=False, nullable=True)

    seller_id = Column(Integer, ForeignKey(Seller.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=True)

    product_id = Column(Integer, ForeignKey(Product.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)

    monitoring_product_id = Column(Integer, ForeignKey(MonitoringProduct.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_seller_id = Column(Integer, ForeignKey(MonitoringSeller.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)


class MonitoredOption(Base):
    __tablename__ = "Monitored_options"
    __table_args__ = (UniqueConstraint("monitoring_id", "option_id", "monitored_product_id"),)

    id = Column(Integer, primary_key=True)

    monitored_product_id = Column(Integer, ForeignKey(MonitoredProduct.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)

    option_id = Column(Integer, ForeignKey(ProductOption.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)

    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)

    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)

    parser_id = Column(Integer, ForeignKey(Parser.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=True)

    parser_parameter = Column(Text(), index=False, unique=False, nullable=True)


class ScanQueueObject(Base):
    __tablename__ = "Scan_queue"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitored_product_id = Column(Integer, ForeignKey(MonitoredProduct.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    retries = Column(Integer, primary_key=False, default=0)


class BaseScanResult(Base):
    __tablename__ = "Base_scan_results"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitored_product_id = Column(Integer, ForeignKey(MonitoredProduct.id, ondelete="CASCADE"), index=True, unique=True, primary_key=False, nullable=False)
    scan_result = Column(Text(), index=False, unique=False, nullable=True)
    scan_error = Column(Text(), index=False, unique=False, nullable=True)
    result_code = Column(Integer, index=True, unique=False, nullable=False)
    last_scan_time = Column(Integer, index=True, unique=False, nullable=False)


class OptionScanResult(Base):
    __tablename__ = "Options_scan_results"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    option_id = Column(Integer, ForeignKey(MonitoredOption.id, ondelete="CASCADE"), index=True, unique=True, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitored_product_id = Column(Integer, ForeignKey(MonitoredProduct.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    scan_result = Column(Text(), index=False, unique=False, nullable=True)
    scan_error = Column(Text(), index=False, unique=False, nullable=True)
    result_code = Column(Integer, index=True, unique=False, nullable=False)
    last_scan_time = Column(Integer, index=True, unique=False, nullable=False)


class ScanReport(Base):
    __tablename__ = "Scan_report"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(), index=True, unique=False, nullable=False);
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    notifications_enabled = Column(Boolean, unique=False, default=True)
    report_time = Column(String(), unique=False, nullable=True)
    days_of_week = Column(Text(), index=False, unique=False, nullable=True)


class ReportStat(Base):
    __tablename__ = "Report_stat"
    __table_args__ = (UniqueConstraint("report_id", "email"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, unique=False, primary_key=False, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    report_id = Column(Integer, ForeignKey(ScanReport.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    email = Column(String(),  ForeignKey(UserEmail.email, ondelete="CASCADE"), unique=False, nullable=True)
    report_time = Column(String(), unique=False, nullable=True)
    report_time_unix = Column(Integer(), unique=False, nullable=True)
    sent_ok = Column(Boolean, unique=False, default=False)
    error = Column(Text(), index=False, unique=False, nullable=True)


class ScanReportSeller(Base):
    __tablename__ = "Scan_report_seller"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    report_id = Column(Integer, ForeignKey(ScanReport.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_seller_id = Column(Integer, ForeignKey(MonitoringSeller.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)


class ScanReportProduct(Base):
    __tablename__ = "Scan_report_product"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    report_id = Column(Integer, ForeignKey(ScanReport.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_product_id = Column(Integer, ForeignKey(MonitoringProduct.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)


class ScanStat(Base):
    __tablename__ = "Scan_stats"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(Project.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    monitoring_id = Column(Integer, ForeignKey(Monitoring.id, ondelete="CASCADE"), index=True, unique=False, primary_key=False, nullable=False)
    last_scan_status = Column(Integer, index=True, unique=False, nullable=False)
    last_scan_errmsg = Column(Text(), index=False, unique=False, nullable=True)
