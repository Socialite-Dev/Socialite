from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators

class LoginForm(FlaskForm):
    username =  StringField("Username", [validators.InputRequired()])
    password =  PasswordField("Password", [validators.InputRequired()])

class RegistrationForm(FlaskForm):
    username =  StringField("Username", [validators.InputRequired()])
    password =  PasswordField("Password", [validators.InputRequired()])
    confirmed_password =  PasswordField("Password Confirmation", [validators.InputRequired(), validators.EqualTo("password")])
    email = StringField("Email", [validators.Email()])
    confirmed_email = StringField("Email", [validators.Email(), validators.EqualTo("email")])

class PostForm(FlaskForm):
    content = StringField("Content", [validators.InputRequired()])
