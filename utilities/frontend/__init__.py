
from flask import Flask
from flask_mail import Mail
import os
from utilities.frontend.database import init_db

mail = Mail()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'secret')
    # app.config.from_pyfile('config.py')  # optional

    # Mail config
    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.getenv('EMAIL_USER'),
        MAIL_PASSWORD=os.getenv('EMAIL_PASS')
    )
    mail.init_app(app)

    # Initialize DB
    init_db()

    # Register routes
    from utilities.frontend.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    from utilities.frontend.routes.chatbot import chatbot_bp
    app.register_blueprint(chatbot_bp)

    return app
