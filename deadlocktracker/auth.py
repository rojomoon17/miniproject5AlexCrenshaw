# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Mini Project 5

import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from deadlocktracker.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")

MAX_USERNAME_LENGTH = 30
MIN_PASSWORD_LENGTH = 6


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        # .get() so a missing field shows a message instead of a 400 error.
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        error = None

        if not username:
            error = "Username is required."
        elif len(username) > MAX_USERNAME_LENGTH:
            error = f"Usernames can be at most {MAX_USERNAME_LENGTH} characters."
        elif not password:
            error = "Password is required."
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f"Passwords must be at least {MIN_PASSWORD_LENGTH} characters."

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                flash("Account created. Log in to start tracking matches.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "danger")

    return render_template("auth/register.html", username=request.form.get("username", ""))


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        error = None
        user = db.execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            error = "Incorrect username or password."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash(error, "danger")

    return render_template("auth/login.html", username=request.form.get("username", ""))


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):
    """Redirect anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Log in to see that page.", "warning")
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view
