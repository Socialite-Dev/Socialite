from flask import Flask, render_template, redirect, make_response, request
from flask_login import current_user

from functools import lru_cache

import forms

import flask_login

import database

from typing import Self

from time import strftime, localtime

app = Flask(__name__)

with open(".flask_key", "r") as f:
    app.secret_key = f.read()

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

@app.template_filter('get_sidebar_user_info')
@lru_cache(maxsize = 1024)
def get_sidebar_user_info(user: int):
    return database.get_sidebar_user_info(user)

@app.template_filter('get_sidebar_group_info')
@lru_cache(maxsize = 1024)
def get_sidebar_group_info(group: int):
    return database.get_sidebar_group_info(group)

@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(timestamp: int):
    return strftime("%A %d %B %Y %I:%M %P", localtime(timestamp / 1000000000)) 

class LoginDummy:
    def __init__(self, id: str):
        self.id = int(id)
        database_result = database.grab_info_for(id)
        if database_result is None:
            raise TypeError("Expected data from the database for user {id}, got None")
        self._username, self._is_teacher = database_result
        self.is_authenticated = True
        self.is_active = True

    @classmethod
    def create(cls, id: str) -> Self | None:
        if not database.user_exists(id):
            return None
        return cls(id)

    def get_id(self) -> str:
        return str(self.id)

@login_manager.user_loader
def load_user(id: str):
    return LoginDummy.create(id)

def get_shared_logged_in_template_values(user: int):
    return {
            "friends": database.get_friends_of(user),
            "groups": database.get_groups_of(user)
    }

@app.route("/")
def index():
    '''Homepage route'''
    if current_user.is_authenticated:
        return render_template("index.html",
            posts = database.generate_feed(current_user.id),
            form = forms.PostForm(),
            **get_shared_logged_in_template_values(current_user.id)
        )
    else:
        return render_template("index.html")
        
@app.route("/login", methods=["GET","POST"])
def login():
    '''Login website page / API route'''
    if current_user.is_authenticated:
        return redirect("/")

    form = forms.LoginForm()
    errors = []
    if form.validate_on_submit():

        db_resp = database.authenticate(form.username.data, form.password.data)
        if db_resp:
            flask_login.login_user(LoginDummy(db_resp))
            return redirect("/")
        errors.append(db_resp)

    return render_template("login.html", form=form, user=current_user, errors=errors)

@app.route("/logout")
def logout():
    '''Logout endpoint - clears session cookie of info'''
    if current_user.is_authenticated:
        flask_login.logout_user()
    return redirect("/")

@app.route("/register", methods=["GET","POST"])
def register(): 
    '''Register website page / API route'''
    if current_user.is_authenticated:
        return redirect("/")

    form = forms.RegistrationForm()
    errors = []
    if form.validate_on_submit():
        if database.register(form.username.data, form.password.data):
            return redirect("/")
        errors.append("failed to register")

    return render_template("register.html", form=form, user=current_user)

def has_permission_to_access_wall(user: int, wall: int):
    return user==wall or database.are_friends(user, wall)

@app.route("/wall/<int:id>")
def render_wall(id: int):
    '''Route for handling generation of a wall's page'''
    if not current_user.is_authenticated:
        return redirect("/", 400)
    
    if not has_permission_to_access_wall(current_user.id, id):
        return redirect("/", 403)
    
    return render_template("wall.html",
                posts=database.posts_to_wall(id),
                wall_owner=database.get_user_by_id(id),
                form=forms.PostForm(),
                **get_shared_logged_in_template_values(current_user.id)
            )

@app.route("/group/<int:id>")
def render_group(id: int):
    '''Route for handling generation of a group's page'''
    if not current_user.is_authenticated:
        return redirect("/", 400)
    
    if not database.is_group_member(current_user.id, id):
        return redirect("/", 403)
    
    return render_template("group.html",
    posts=database.posts_to_group(id),
                group=database.get_sidebar_group_info(id),
                form=forms.PostForm(),
                is_admin=database.is_group_admin(current_user.id, id),
                **get_shared_logged_in_template_values(current_user.id)
            )

@app.route("/post/<string:target_t>/<int:id>", methods=["POST"])
def post_handler(target_t: str, id: int):
    '''POST endpoint to make a post'''
    if not current_user.is_authenticated:
        return redirect("/", 401)

    post = None
    form = forms.PostForm()
    if form.validate_on_submit():
        if target_t == "wall":
            if not has_permission_to_access_wall(current_user.id, id):
                return make_response("Failed", 403)
            
            post = database.post_to_wall(current_user.id, form.content.data, id)
        elif target_t == "group":
            if not database.is_group_member(current_user.id, id):
                return make_response("Failed", 403)

            post = database.post_to_group(current_user.id, form.content.data, id)

        else:
            return make_response("Failed", 400)
        
        if post is not None:
            return { "elem" : render_template("post.html", post=post) }
    
    return make_response("Failed", 400)

@app.route("/comment/<string:target_t>/<int:id>", methods=["POST"])
def comment_handler(target_t: str, id: int):
    '''POST endpoint to create comments on a post'''
    if not current_user.is_authenticated:
        return redirect("/", 401)

    post = None
    form = forms.PostForm()
    if form.validate_on_submit():
        if target_t == "wall":
            print(f"{current_user.id=} {id=}")
            if not database.can_comment_on_wall_post(current_user.id, id):
                return make_response("Failed", 403)
            
            post = database.comment_to_wall(current_user.id, form.content.data, id)
        elif target_t == "group":
            if not database.can_comment_on_group_post(current_user.id, id):
                return make_response("Failed", 403)

            post = database.comment_to_group(current_user.id, form.content.data, id)

        else:
            return make_response("Failed", 400)
        
        if post is not None:
            return { "elem" : render_template("comment.html", comment=post) }
    
    return make_response("Failed", 400)

@app.route("/posts/<string:target_t>/<int:id>")
def detailed_post(target_t: str, id: int):
    '''Renders detailed view of a post'''
    if current_user.is_authenticated and database.can_see_detail_on_post(target_t, current_user.id, id):
        comments = None
        post = None
        is_admin = None

        if target_t == "wall":
            post = database.get_wall_post(id)
            comments = database.get_wall_post_comments(id)
            is_admin = database.is_wall_post_admin(current_user.id, id)
        else:
            post = database.get_group_post(id)
            comments = database.get_group_post_comments(id)
            is_admin = database.is_group_admin(current_user.id, id)

        if post is None:
            print(f"{comments=} {post=}")
            return redirect("/")

        print(f"{post=}")

        return render_template("post_detail.html",
            post = post,
            comments = comments,
            form = forms.PostForm(),
            target_t = target_t,
            is_admin = is_admin,
            **get_shared_logged_in_template_values(current_user.id)
        )
    else:
        print(f"{target_t=}")
        if target_t == "wall":
            print(f"{current_user.id=} {id=}")
            print(f"{has_permission_to_access_wall(current_user.id, id)=}")
        else:
            print(f"{database.is_group_member(current_user.id, id)=}")
        return redirect("/", 401)

@app.route("/friend_request", methods=["POST", "GET"])
def friend_request():
    '''Handles page for making a friend request and provides POST endpoint to add request into model'''
    if not current_user.is_authenticated:
        return redirect("/")
   
    form = forms.FriendRequest()

    if form.validate_on_submit():
        res = database.friend_request(current_user.id, form.name.data)
        print(f"friend_request {res=}")
        return redirect("/")

    return render_template("friend_request.html", form=form, **get_shared_logged_in_template_values(current_user.id))

@app.route("/friend_request/<int:id>")
def friend_request_splash(id: int):
    '''Renders page for displaying existing friend request info'''
    if not current_user.is_authenticated:
        return redirect("/")
   
    other = database.requester(current_user.id, id) 
    if other is None:
        return redirect("/")

    other = other[0]
    made = other == current_user.id

    return render_template("friend_request_splash.html", made = made, other = other, **get_shared_logged_in_template_values(current_user.id))

@app.route("/accept_friendship/<int:id>")
def accept_friend_request(id: int):
    '''Endpoint to accept a friend request'''
    if not current_user.is_authenticated:
        return redirect("/")
    
    database.accept_friend_request(current_user.id, id)
    return redirect("/")

@app.route("/end_friendship/<int:id>")
def end_friendship(id: int):
    '''Endpoint to end a friendship / reject friend request'''
    if not current_user.is_authenticated:
        return redirect("/")

    database.end_friendship(current_user.id, id)
    return redirect("/")

@app.route("/group_join", methods = ["POST", "GET"])
def join_group():
    '''Renders webpage / handles POST request to join / create a group'''
    if not current_user.is_authenticated:
        return redirect("/")

    create_form = forms.CreateGroup()
    join_form = forms.JoinGroup()

    if create_form.validate_on_submit():
        database.create_group(current_user.id, create_form.name.data)
        return redirect("/")

    if join_form.validate_on_submit():
        database.join_group(current_user.id, join_form.id.data)
        return redirect("/")

    return render_template("group_join.html", create_form=create_form, join_form=join_form, **get_shared_logged_in_template_values(current_user.id))

@app.route("/delete_group", methods = ["POST"])
def delete_group():
    '''POST endpoint to handle group deletion'''
    if current_user.is_authenticated:
        if database.is_group_admin(current_user.id, request.json['id']):
            if database.delete_group(request.json['id']):
                return make_response("SUCCESS", 200) 

    return make_response("FAILED", 500)

@app.route("/rename", methods = ["GET", "POST"])
def rename():
    '''Renders page for / handles POST request to rename username'''
    if not current_user.is_authenticated:
        return redirect("/")

    form = forms.RenameForm()
    if form.validate_on_submit():
        database.rename(current_user.id, form.name.data)
        get_sidebar_user_info.cache_clear()
        return redirect("/")

    return render_template("rename.html", form=form, **get_shared_logged_in_template_values(current_user.id))

@app.route("/delete_post", methods = ["POST"])
def delete_post():
    '''POST endpoint for an admin / wall owner to delete a post'''
    if current_user.is_authenticated:
        if database.delete_post(request.json['target_t'], request.json['post_id']):
            return make_response("SUCCESS", 200)
    return make_response("FAILED", 500) 
