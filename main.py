from datetime import date
from functools import wraps
import os

from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Initialize SQLAlchemy
db = SQLAlchemy()


# Define database models
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    post = relationship("BlogPost", back_populates="comments")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

# Create database if not exists
if not os.path.exists('instance'):
    os.makedirs('instance')

app.config['SQLALCHEMY_DATABASE_URI'] ="sqlite:///" + os.path.abspath(os.path.join(os.path.dirname(__file__), 'instance/posts.db'))

db.init_app(app)

# Create all tables
with app.app_context():
    db.create_all()


# Flask-Login loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        user = User.query.filter_by(email=email).first()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        new_user = User(email=form.email.data, password=hashed_password, name=form.name.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


# Login route
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, form.password.data):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


# Logout route
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


# Home page route
@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=True)


# Individual post route with comment functionality
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        new_comment = Comment(text=form.comment_text.data, comment_author=current_user, post=post)
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post.id))
    return render_template("post.html", post=post, form=form, current_user=current_user)


# Only allow admin to access this route
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


# Route to add a new post (admin only)
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


# Route to edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    form = CreatePostForm(obj=post)
    if form.validate_on_submit():
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.body = form.body.data
        post.img_url = form.img_url.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=form, is_edit=True, current_user=current_user)


# Route to delete a post (admin only)
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# About page route
@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


# Contact page route
@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=False)
    