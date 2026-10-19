# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Mini Project 5

import os

from flask import Flask


def create_app(test_config=None):
    """Application factory: create and configure the Flask app."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # Override SECRET_KEY in instance/config.py for anything beyond local dev.
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "deadlocktracker.sqlite"),
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    from . import matches
    app.register_blueprint(matches.bp)
    app.add_url_rule("/", endpoint="index")

    from . import errors
    app.register_blueprint(errors.bp)

    return app
