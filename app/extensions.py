from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

# Single shared instances — imported by app/__init__.py and by models/routes.
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
