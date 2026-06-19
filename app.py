import os

import requests
from flask import Flask, abort, render_template
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate

from admin import admin_bp
from app_config import DATABASE_URI, SECRET_KEY
from auth import auth_blueprint
from mc_server import server_api
from models import db, PlayerServerAccess, Server, User
from player_view import player_api
from routes_mods import mods_api
from routes_notices import notices_api

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Databáze a přihlášení
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)
db.init_app(app)

# Inicializace migrací
migrate = Migrate(app, db)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Blueprinty
app.register_blueprint(auth_blueprint)
app.register_blueprint(server_api)
app.register_blueprint(mods_api)
app.register_blueprint(notices_api)
app.register_blueprint(player_api)
app.register_blueprint(admin_bp)


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user

    # Servery, které vlastní
    owned = user.owned_servers

    # Servery, kde je admin, ale není vlastník
    admin_only = user.admin_of_servers.filter(Server.owner_id != user.id).all()

    # Servery, ke kterým má přístup jako hráč
    player_access = user.accessible_servers_as_player

    # Sloučení bez duplicit podle ID serveru
    servers_dict = {}
    for server in owned:
        servers_dict[server.id] = {'server': server, 'role': 'owner'}
    for server in admin_only:
        if server.id not in servers_dict:
            servers_dict[server.id] = {'server': server, 'role': 'admin'}
    for server in player_access:
        if server.id not in servers_dict:
            servers_dict[server.id] = {'server': server, 'role': 'player'}

    # Získání IP adresy
    try:
        ip_address = requests.get("https://api.ipify.org", timeout=3).text
    except requests.RequestException:
        ip_address = "localhost"

    servers_data = []
    for item in servers_dict.values():
        server = item['server']
        servers_data.append({
            "id": server.id,
            "name": server.name,
            "loader": server.build_version.build_type.name if server.build_version else None,
            "mc_version": server.build_version.mc_version if server.build_version else None,
            "ip": ip_address,
            "port": server.server_port,
            "role": item['role'],
        })

    return render_template(
        "dashboard.html",
        username=user.username,
        servers=servers_data,
    )


@app.route('/server/<int:server_id>')
@login_required
def server_panel(server_id):
    server = Server.query.get_or_404(server_id)

    # Ověření přístupu - vlastník, admin nebo hráč s přístupem
    has_access = (
        server.owner_id == current_user.id
        or current_user in server.admins
        or PlayerServerAccess.query.filter_by(
            user_id=current_user.id,
            server_id=server_id,
        ).first() is not None
    )

    if not has_access:
        abort(403)

    return render_template("includes/_server_panel.html", server=server)


@app.route('/server/<int:server_id>/plugins')
@login_required
def server_plugins(server_id):
    server = Server.query.get_or_404(server_id)

    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    return render_template("plugins_manager.html", server=server)


@app.route('/server/<int:server_id>/mods')
@login_required
def server_mods(server_id):
    server = Server.query.get_or_404(server_id)
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    return render_template("mods_manager.html", server=server)


if __name__ == '__main__':
    if not os.path.exists('db.sqlite3'):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
