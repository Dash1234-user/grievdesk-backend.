from app.routes.auth import auth_bp
from app.routes.chat import chat_bp
from app.routes.complaints import complaints_bp
from app.routes.users import users_bp
from app.routes.rules import rules_bp
from app.routes.announcements import announcements_bp
from app.routes.notifications import notifications_bp
from app.routes.service_requests import service_requests_bp
from app.routes.dues import dues_bp
from app.routes.amenities import amenities_bp, bookings_bp
from app.routes.my_tickets import my_tickets_bp
from app.routes.search import search_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(announcements_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(service_requests_bp)
    app.register_blueprint(dues_bp)
    app.register_blueprint(amenities_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(my_tickets_bp)
    app.register_blueprint(search_bp)
