from flask import Blueprint, render_template, request, redirect, session, url_for
from utilities.frontend.database import get_connection
from utilities.frontend.security import hash_password, check_password, is_strong_password
import pyodbc
import secrets
from flask_mail import Mail, Message
import os
import dotenv
from flask import current_app
from utilities.frontend import mail
dotenv.load_dotenv()

auth_bp = Blueprint('auth', __name__)

reset_tokens = {}

@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not is_strong_password(password):
            return "Password too weak. Must have 8+ chars, upper/lowercase, digit & special char."

        hashed_pw = hash_password(password)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO dbo.AgentLaw_UserDB (username, email, password) VALUES (?, ?, ?)',
                           (username, email, hashed_pw))
            conn.commit()
            return redirect(url_for('auth.login'))
        except pyodbc.IntegrityError:
            return "Email or username already exists"
        finally:
            conn.close()
    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM dbo.AgentLaw_UserDB WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password(password, user[0]):
            session['user'] = email
            return redirect(url_for('chatbot.main'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@auth_bp.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        token = secrets.token_urlsafe(16)
        reset_tokens[email] = token

        msg = Message("Password Reset",
                      sender=current_app.config['MAIL_USERNAME'],
                      recipients=[email])
        link = url_for('auth.reset_password', email=email, token=token, _external=True)
        msg.body = f"Click the link to reset your password:\n{link}"
        mail.send(msg)
        return "Password reset email sent!"
    return render_template('forgot_password.html')

@auth_bp.route('/reset/<email>/<token>', methods=['GET', 'POST'])
def reset_password(email, token):
    if email not in reset_tokens or reset_tokens[email] != token:
        return "Invalid or expired token"

    if request.method == 'POST':
        new_password = request.form['new_password']
        if not is_strong_password(new_password):
            return "Password too weak. Try again."

        hashed_pw = hash_password(new_password)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE dbo.AgentLaw_UserDB SET password = ? WHERE email = ?', (hashed_pw, email))
        conn.commit()
        conn.close()
        reset_tokens.pop(email)
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth.login'))

