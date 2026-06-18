from flask import Blueprint, render_template, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from models import db, User, Server, BuildType, BuildVersion, Plugin, Mod
from mc_server import (
    get_server_status,
    start_server,
    stop_server,
    restart_server,
    total_cores,
    JAVA_EXECUTABLE,
)
import subprocess
import sys
import os
import re
from server_creator import SERVICE_LEVELS, create_server_from_payload

try:
    import psutil
except ImportError:
    psutil = None

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def _build_cpu_affinity_summary(servers):
    cores = [{'index': index, 'servers': []} for index in range(total_cores or 0)]

    for server in servers:
        status = get_server_status(server.id)
        assigned_cores = status.get('assigned_cores') or []

        if not assigned_cores and psutil and status.get('status') == 'running' and status.get('pid'):
            try:
                affinity = psutil.Process(status['pid']).cpu_affinity()
                if len(affinity) < (total_cores or len(affinity)):
                    assigned_cores = affinity
            except Exception:
                assigned_cores = []

        for core in assigned_cores:
            if isinstance(core, int) and 0 <= core < len(cores):
                cores[core]['servers'].append(server.name)

    used_count = sum(1 for core in cores if core['servers'])
    return {
        'total': len(cores),
        'used': used_count,
        'free': max(len(cores) - used_count, 0),
        'cores': cores,
    }


def _get_java_runtime_info():
    try:
        result = subprocess.run(
            [JAVA_EXECUTABLE, '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stderr or result.stdout or '').strip()
        first_line = output.splitlines()[0] if output else 'Java verze nebyla zjištěna'
        match = re.search(r'version "([^"]+)"', first_line)
        version = match.group(1) if match else first_line
        major_text = version.split('.')[0]
        major = int(major_text) if major_text.isdigit() else None
        return {
            'executable': JAVA_EXECUTABLE,
            'version': version,
            'major': major,
            'warning': major is not None and major < 25
        }
    except Exception as e:
        return {
            'executable': JAVA_EXECUTABLE,
            'version': 'Neznámá',
            'major': None,
            'warning': True,
            'error': str(e)
        }

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
    servers = Server.query.order_by(Server.id.asc()).all()
    users = User.query.order_by(User.username.asc()).all()
    build_types = BuildType.query.order_by(BuildType.name.asc()).all()
    build_versions = BuildVersion.query.join(BuildType).order_by(
        BuildType.name.asc(),
        BuildVersion.mc_version.desc(),
        BuildVersion.build_number.desc()
    ).all()
    cpu_summary = _build_cpu_affinity_summary(servers)
    return render_template(
        'admin/servers.html',
        servers=servers,
        users=users,
        build_types=build_types,
        build_versions=build_versions,
        service_levels=SERVICE_LEVELS,
        cpu_summary=cpu_summary,
        java_info=_get_java_runtime_info()
    )


@admin_bp.route('/server/create', methods=['POST'])
@login_required
@admin_required
def create_server():
    try:
        success, message, server = create_server_from_payload(request.get_json() or {})
        if not success:
            return jsonify({'success': False, 'error': message}), 400

        return jsonify({
            'success': True,
            'message': message,
            'server_id': server.id
        })
    except Exception as e:
        current_app.logger.exception('Vytvo?en? serveru selhalo')
        return jsonify({'success': False, 'error': str(e)}), 500

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
    build_types = BuildType.query.order_by(BuildType.name.asc()).all()
    total_builds = BuildVersion.query.count()
    build_cards = []

    for build_type in build_types:
        versions = sorted(
            build_type.versions,
            key=lambda v: (
                v.mc_version or '',
                v.created_at.isoformat() if v.created_at else '',
                v.build_number or ''
            ),
            reverse=True
        )
        grouped_versions = {}
        for version in versions:
            grouped_versions.setdefault(version.mc_version or 'Neznámá verze', []).append(version)

        build_cards.append({
            'type': build_type,
            'count': len(versions),
            'mc_version_count': len(grouped_versions),
            'groups': grouped_versions
        })

    return render_template(
        'admin/builds.html',
        build_types=build_types,
        build_cards=build_cards,
        total_builds=total_builds
    )

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
