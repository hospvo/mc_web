from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_user, logout_user, login_required
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash

auth_blueprint = Blueprint('auth', __name__)

# Registrace
@auth_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Heslo zašifrujeme
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Vytvoříme nového uživatele
        new_user = User(username=username, email=email, password=hashed_password, is_active_db=True)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('auth.login'))

    return render_template('register.html')

# Přihlášení
@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Hledáme uživatele v databázi
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            print("Uživatel nalezen a heslo je správné.")
            print("is_active:", user.is_active)
            login_user(user)
            next_page = request.args.get('next')
            print("Redirecting to:", next_page)
            return redirect(url_for('dashboard'))
        else:
            print("Neplatné přihlášení.")

    return render_template('login.html')

# Odhlášení
@auth_blueprint.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
