from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField


class LoginForm(FlaskForm):
    username = StringField('username')
    password = PasswordField('password')


class ProjectForm(FlaskForm):
    name = StringField('name')

class SellerForm(FlaskForm):
    name = StringField('name')

class ProductForm(FlaskForm):
    name = StringField('name')
    option_name = StringField('option name')
    option_val = TextAreaField('option')

class ParserForm(FlaskForm):
    name = StringField('name')
    parser_code = TextAreaField('code')
