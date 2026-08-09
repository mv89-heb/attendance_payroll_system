import logging
from flask import Flask, jsonify, session, g
from app.config import Config
from app.db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger(__name__)

def create_app(config_class=Config) -> Flask:
    app = Flask(
        __name__, 
        template_folder="web/templates", 
        static_folder="web/static"
    )
    app.config.from_object(config_class)

    db.init_app(app)

    # רישום הבקריות
    from app.web.blueprints.auth import auth_bp
    from app.web.blueprints.views import views_bp
    from app.web.blueprints.kiosk import kiosk_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(views_bp)
    app.register_blueprint(kiosk_bp)

    @app.before_request
    def load_session_user():
        g.user = session.get("user")

    @app.after_request
    def apply_secure_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.route("/health", methods=["GET"])
    def health_check():
        try:
            with db.cursor() as cur:
                cur.execute("SELECT 1;")
            return jsonify({"status": "healthy", "database": "connected"}), 200
        except Exception as e:
            err_type = type(e).__name__
            logger.error("Database health check failed")
            logger.error(f"type: {err_type}")
            logger.error(f"reason: {str(e)}")
            return jsonify({
                "status": "unhealthy", 
                "database": "unavailable",
                "error_type": err_type
            }), 500

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad Request", "details": str(e.description)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource Not Found"}), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"error": "Internal Server Error"}), 500

    return app