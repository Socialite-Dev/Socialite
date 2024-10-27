from flask import Flask, render_template, make_response, redirect
from flask_login import LoginManager
import flask_login

import database
import forms

from typing import Self

import logging
logger = logging.getLogger(__name__)

app = Flask(__name__)

with open(".flask_key","r") as f:
    app.secret_key = f.read()

login_manager = LoginManager()
login_manager.init_app(app)

class LoginDummy:
    def __init__(self, id: str) -> Self:
        self.id = int(id)
        self.username: str | None = None
        self.is_admin: str | None = None
        self.is_teacher: str | None = None

    @classmethod
    def create(cls, id: str) -> Self | None:
        if not database.user_exists(id):
            return None
        return cls(id)

    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_authenticated(self) -> bool:
        return True
    
    @property
    def is_active(self) -> bool:
        return True
    
    @property
    def is_anonymous(self) -> bool:
        return False

    def _get_details(self) -> None:
        (self.username, self.is_admin, self.is_teacher) = database.fill_user_dummy(self.id)

    def get_username(self) -> str:
        if self.username is None:
            self._get_details()
        return self.username

    def get_is_admin(self) -> str:
        if self.is_admin is None:
            self._get_details()
        return self.is_admin

    def get_is_teacher(self) -> str:
        if self.is_teacher is None:
            self._get_details()
        return self.is_teacher

user_cache = {}

@login_manager.user_loader
def load_user(id: str) -> LoginDummy | None:
    if id in user_cache:
        return user_cache[id]

    dummy = LoginDummy.create(id)
    if dummy is not None:
        user_cache[id] = dummy

    return dummy

@app.route("/")
def index():
    if flask_login.current_user.is_authenticated:
        return render_template("feed.html",
            user=flask_login.current_user,
            posts = database.generate_feed(flask_login.current_user.id),
            form = forms.PostForm())

    return render_template("landing.html", user=flask_login.current_user)

@app.route("/login", methods=["GET","POST"])
def login(): 
    if flask_login.current_user.is_authenticated:
        return redirect("/")

    form = forms.LoginForm()
    if form.validate_on_submit():

        # Wish we got `if let` in python
        db_resp = database.authenticate(form.username.data, form.password.data)
        if db_resp:
            flask_login.login_user(LoginDummy(db_resp.id))
            return redirect("/")

    return render_template("login.html", form=form, user=flask_login.current_user)

@app.route("/register", methods=["GET","POST"])
def register(): 
    if flask_login.current_user.is_authenticated:
        return redirect("/")

    form = forms.RegistrationForm()
    if form.validate_on_submit():
        if database.register(form.username.data, form.password.data, form.email.data):
            return redirect("/")

    return render_template("register.html", form=form, user=flask_login.current_user)

@app.route("/post", methods=["POST"])
def post():
    if not flask_login.current_user.is_authenticated:
        return make_response("Unauthenticated", 401)
    
    form = forms.PostForm()
    if form.validate_on_submit():
        #TODO: Think about whether this is fine to do
        #I think it is but I'm not 100% sure
        database.trusting_post(flask_login.current_user.id, form.content)

if __name__ == "__main__":
    app.run("127.0.0.1", debug=True)
