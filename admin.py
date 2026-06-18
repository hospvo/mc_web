from flask import Blueprint, render_template, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from models import db, User, Server, BuildType, BuildVersion, Plugin, Mod
from mc_server import get_server_status, start_server, stop_server, restart_server
import subprocess
import sys
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/')
@login_required
@admin_required
def index():
    # Dashboard s přehledy
    servers = Server.query.all()
    users = User.query.count()
    plugins = Plugin.query.count()
    mods = Mod.query.count()
    builds = BuildVersion.query.count()
    return render_template('admin/index.html', 
                         servers=servers, 
                         users=users, 
                         plugins=plugins, 
                         mods=mods, 
                         builds=builds)

@admin_bp.route('/servers')
@login_required
@admin_required
def servers():
    servers = Server.query.all()
    return render_template('admin/servers.html', servers=servers)

@admin_bp.route('/server/<int:server_id>/action', methods=['POST'])
@login_required
@admin_required
def server_action(server_id):
    action = request.json.get('action')
    if action == 'start':
        success = start_server(server_id)
    elif action == 'stop':
        success = stop_server(server_id)
    elif action == 'restart':
        success = restart_server(server_id)
    else:
        return jsonify({'success': False, 'error': 'Unknown action'})
    return jsonify({'success': success})

@admin_bp.route('/server/<int:server_id>/status')
@login_required
@admin_required
def server_status(server_id):
    status = get_server_status(server_id)
    return jsonify(status)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/user/<int:user_id>/make-admin', methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_superadmin = True
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/user/<int:user_id>/remove-admin', methods=['POST'])
@login_required
@admin_required
def remove_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot remove yourself'})
    user.is_superadmin = False
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot delete yourself'})
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/builds')
@login_required
@admin_required
def builds():
    build_types = BuildType.query.all()
    return render_template('admin/builds.html', build_types=build_types)

@admin_bp.route('/sync/<build_name>', methods=['POST'])
@login_required
@admin_required
def sync_build(build_name):
    from sync_paper import run_sync as sync_paper
    from sync_folia import run_sync as sync_folia
    from sync_fabric import run_sync as sync_fabric
    from sync_forge import run_sync as sync_forge
    try:
        if build_name.upper() == 'PAPER':
            result = sync_paper()
        elif build_name.upper() == 'FOLIA':
            result = sync_folia()
        elif build_name.upper() == 'FABRIC':
            result = sync_fabric()
        elif build_name.upper() == 'FORGE':
            result = sync_forge()
        else:
            return jsonify({'success': False, 'error': 'Unknown build type'})
        return jsonify({'success': True, 'message': result.get('message')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/run-script', methods=['POST'])
@login_required
@admin_required
def run_script():
    script = request.json.get('script')
    allowed = ['create_data.py', 'manage.py']  # jen pro ukázku
    if script not in allowed:
        return jsonify({'success': False, 'error': 'Script not allowed'})
    try:
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        return jsonify({'success': True, 'output': result.stdout, 'error': result.stderr})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/mods')
@login_required
@admin_required
def mods():
    """Seznam všech modů v systému."""
    # Načteme všechny mody i s informacemi o serverech (volitelně)
    mods = Mod.query.order_by(Mod.display_name, Mod.name).all()
    return render_template('admin/mods.html', mods=mods)

@admin_bp.route('/mod/<int:mod_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_mod(mod_id):
    """Smazání modu (soubor i záznam)."""
    mod = Mod.query.get_or_404(mod_id)
    
    # Odstranění fyzického souboru, pokud existuje
    if mod.file_path and os.path.exists(mod.file_path):
        try:
            os.remove(mod.file_path)
        except Exception as e:
            current_app.logger.error(f"Nelze smazat soubor modu {mod.name}: {e}")
    
    # Smazání vazeb M:N s modpacky a servery (automaticky díky cascade?)
    # V modelech není definováno cascade, ručně vyčistíme spojovací tabulky
    mod.servers = []   # odstraní vazby M:N
    # Odebrat z modpacků (mod_pack_mods)
    from models import mod_pack_mods
    db.session.execute(mod_pack_mods.delete().where(mod_pack_mods.c.mod_id == mod_id))
    
    db.session.delete(mod)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Mod {mod.name} byl smazán'})