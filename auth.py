from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash 

auth_blueprint = Blueprint('auth', __name__)

# Registrace
@auth_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # Základní validace (můžete doplnit)
        if not username or not email or not password:
            flash('Všechna pole jsou povinná.', 'error')
            return render_template('register.html', username=username, email=email)

        # Kontrola, zda uživatel nebo email již existuje
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            if existing_user.username == username:
                flash('Uživatelské jméno je již obsazeno. Zvolte prosím jiné.', 'error')
            else:
                flash('Email je již registrován. Použijte jiný email nebo se přihlaste.', 'error')
            return render_template('register.html', username=username, email=email)

        # Heslo zašifrujeme
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Vytvoříme nového uživatele
        new_user = User(username=username, email=email, password=hashed_password, is_active_db=True)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registrace proběhla úspěšně. Nyní se můžete přihlásit.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

# Přihlášení
@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Úspěšně přihlášen!', 'success')
            return redirect(url_for('dashboard'))
        else:
            # Lepší zpětná vazba
            flash('Neplatné uživatelské jméno nebo heslo', 'error')
            return render_template('login.html')  # Zachovat vyplněné údaje
    
    return render_template('login.html')

# Odhlášení
@auth_blueprint.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
