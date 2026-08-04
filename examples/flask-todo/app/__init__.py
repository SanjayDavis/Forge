"""Flask app factory for the task manager."""
import os
from flask import Flask, jsonify


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite"),
    )
    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import db
    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
