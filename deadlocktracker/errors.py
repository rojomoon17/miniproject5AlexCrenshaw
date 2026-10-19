# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Mini Project 5

import sqlite3

from flask import Blueprint, current_app, g, render_template
from werkzeug.exceptions import HTTPException

bp = Blueprint("errors", __name__)

# Friendly title and message for each HTTP status the app can return.
MESSAGES = {
    400: ("Bad request", "Something about that request didn't look right. Go back and try again."),
    403: ("Not allowed", "You don't have permission to see that. Matches can only be viewed or "
                         "changed by the player who logged them."),
    404: ("Page not found", "We couldn't find what you were looking for. It may have been deleted, "
                            "or the link may be wrong."),
    405: ("Not allowed", "That page can't be used that way. Use the buttons and links in the app."),
    409: ("Couldn't save", "That change conflicts with data that's already saved. Go back and try again."),
    500: ("Something went wrong", "An unexpected error happened on our end. Your saved matches "
                                  "are safe. Try again in a moment."),
    503: ("Database unavailable", "The database couldn't be reached. Try again in a moment."),
}


def render_error(code, message=None, title=None):
    default_title, default_message = MESSAGES.get(code, ("Error", "Something went wrong."))
    return render_template(
        "errors/error.html",
        code=code,
        title=title or default_title,
        message=message or default_message,
    ), code


@bp.app_errorhandler(HTTPException)
def handle_http_error(e):
    """404s, 403s and other HTTP errors, including abort(...) calls in the views."""
    if e.code >= 500:
        current_app.logger.error("Server error: %s", getattr(e, "original_exception", e))
    # abort(404, "message") sets a custom description; otherwise use the default text.
    custom = e.description if e.description != type(e).description else None
    return render_error(e.code, message=custom)


@bp.app_errorhandler(sqlite3.DatabaseError)
def handle_database_error(e):
    """Database problems: missing tables, a locked or corrupt file, or a constraint failure."""
    current_app.logger.exception("Database error")

    db = g.get("db")
    if db is not None:
        try:
            db.rollback()
        except sqlite3.Error:
            pass
    # Don't touch the database again while rendering the error page.
    g.user = None

    if isinstance(e, sqlite3.IntegrityError):
        return render_error(409)
    if "no such table" in str(e):
        return render_error(
            503,
            title="Database not set up",
            message="The database hasn't been initialized yet. Run "
                    "\"flask --app deadlocktracker init-db\", then reload this page.",
        )
    return render_error(503)
