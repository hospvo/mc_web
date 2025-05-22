import os
import subprocess
import psutil
import shutil
import signal
from datetime import datetime
import time
import threading
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Server, User

# Base directory where all server folders will be stored
BASE_SERVERS_PATH = r"C:\Users\hospv\Documents"
#seznam aktuálně využitých jader
USED_CPU = []
total_cores = psutil.cpu_count(logical=True)  # fyzická jádra, nebo True pro logická

class ServerInstance:
    """Třída pro správu stavu jednoho serveru"""
    def __init__(self, server_id):
        self.server_id = server_id
        self.process = None
        self.console_output = []
        self.lock = threading.Lock()  # Pro thread-safe operace
        self.assigned_cores = []
        
    def add_output_line(self, line):
        with self.lock:
            self.console_output.append(line)
            # Udržujeme maximálně 1000 řádků výstupu
            if len(self.console_output) > 1000:
                self.console_output.pop(0)
    
    def get_output(self, lines=50):
        with self.lock:
            return self.console_output[-lines:] if lines > 0 else self.console_output.copy()
        
    # work with cores
    def set_assigned_cores(self, cores):
        """Nastaví přiřazená jádra pro tento server"""
        with self.lock:
            self.assigned_cores = cores.copy()

    def get_assigned_cores(self):
        """Vrátí přiřazená jádra pro tento server"""
        with self.lock:
            return self.assigned_cores.copy()
        
    def release_cores(self):
        """Uvolní přiřazená jádra"""
        with self.lock:
            for core in self.assigned_cores:
                if core in USED_CPU:
                    USED_CPU.remove(core)
            self.assigned_cores = []
        
class ServerManager:
    """Třída pro správu všech server instancí"""
    def __init__(self):
        self.instances = {}  # {server_id: ServerInstance}
        self.instances_lock = threading.Lock()
    
    def get_instance(self, server_id):
        """Získá instanci serveru, vytvoří novou pokud neexistuje"""
        with self.instances_lock:
            if server_id not in self.instances:
                self.instances[server_id] = ServerInstance(server_id)
            return self.instances[server_id]
    
    def remove_instance(self, server_id):
        """Odstraní instanci serveru"""
        with self.instances_lock:
            if server_id in self.instances:
                del self.instances[server_id]

# Globální manager pro všechny servery
server_manager = ServerManager()

def get_server_paths(server_id):
    """Get server-specific paths based on server ID"""
    server = Server.query.get(server_id)
    if not server:
        return None
    
    server_name = server.name.replace(' ', '_').lower()
    server_dir = os.path.join(BASE_SERVERS_PATH, server_name)
    
    return {
        'server_path': os.path.join(server_dir, "minecraft-server"),
        'backup_path': os.path.join(server_dir, "mcbackups"),
        'server_jar': f"server_{server_id}.jar"  # Unikátní název podle server_id
    }

def get_server_status(server_id):
    """Get status of a specific server"""
    paths = get_server_paths(server_id)
    if not paths:
        return {'status': 'error', 'message': 'Server not found'}

    jar_name = paths['server_jar']
    server = Server.query.get(server_id)
    if not server:
        return {'status': 'error', 'message': 'Server config not found'}

    CPU_max_usage = {
        1: '100 %',
        2: '200 %',
        3: '300 %'
    }.get(server.service_level, '100 %')

    # Kontrola přes náš manager
    instance = server_manager.get_instance(server_id)
    if instance.process and instance.process.poll() is None:
        try:
            proc = psutil.Process(instance.process.pid)
            if jar_name in ' '.join(proc.cmdline()):
                mem = proc.memory_info()
                cpu = proc.cpu_percent(interval=0.1)
                print(f"1 cpu percent is {cpu}")
                print(f"cpu max{CPU_max_usage}")
                return {
                    'status': 'running',
                    'pid': proc.pid,
                    'ram_used_mb': round(mem.rss / (1024 ** 2)),
                    'cpu_percent': round(cpu, 1) if cpu >= 0.1 else 0.0,
                    'since': datetime.fromtimestamp(proc.create_time()).strftime('%d.%m.%Y %H:%M'),
                    'port': 25565,
                    'cpu_max': CPU_max_usage
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            if instance.get_assigned_cores():
                print(f"Upozornění: Server {server_id} má přiřazená jádra, ale proces neběží. Uvolňuji jádra.")
                instance.release_cores()
                instance.process = None

    # Fallback - hledání procesů v systému
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            if 'java' in proc.info['name'].lower() and jar_name in cmdline:
                mem = proc.memory_info()
                cpu = proc.cpu_percent(interval=0.1)
                print(f"2 cpu percent is {cpu}")
                print(f"2 cpu max{CPU_max_usage}")
                return {
                    'status': 'running',
                    'pid': proc.pid,
                    'ram_used_mb': round(mem.rss / (1024 ** 2)),
                    'cpu_percent': round(cpu, 1) if cpu >= 0.1 else 0.0,
                    'since': datetime.fromtimestamp(proc.info['create_time']).strftime('%d.%m.%Y %H:%M'),
                    'port': 25565,
                    'cpu_max': CPU_max_usage
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if instance.get_assigned_cores():
        print(f"Upozornění: Server {server_id} má přiřazená jádra, ale neběží. Uvolňuji jádra.")
        instance.release_cores()
        
    return {
        'status': 'stopped',
        'cpu_max': CPU_max_usage
    }



def get_online_players(server_id):
    """Get online players count for specific server"""
    paths = get_server_paths(server_id)
    if not paths:
        return 0
        
    log_path = os.path.join(paths['server_path'], "logs", "latest.log")
    if not os.path.exists(log_path):
        return 0
        
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in reversed(f.readlines()[-500:]):  # Read last 500 lines
            if "joined the game" in line:
                parts = line.split()
                return int(parts[parts.index("There")+2])  # Parse player count
    return 0

def get_backups(server_id):
    """Get backups for specific server"""
    paths = get_server_paths(server_id)
    if not paths or not os.path.exists(paths['backup_path']):
        return []
    
    backups = []
    for entry in os.scandir(paths['backup_path']):
        if entry.is_dir():
            try:
                backups.append({
                    'name': entry.name,
                    'date': datetime.fromtimestamp(entry.stat().st_mtime).strftime('%d.%m.%Y %H:%M'),
                    'size_mb': round(get_folder_size(entry.path) / (1024 ** 2))
                })
            except Exception as e:
                print(f"Error reading backup {entry.name}: {e}")
    return sorted(backups, key=lambda x: x['date'], reverse=True)

def get_folder_size(path):
    """Recursive folder size calculation"""
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_folder_size(entry.path)
    return total

def start_server(server_id):
    """Start a specific server"""
    global USED_CPU
    paths = get_server_paths(server_id)
    if not paths:
        return False
    
    server = Server.query.get(server_id)
    if not server:
        return {'status': 'error', 'message': 'Server config not found'}
    
    instance = server_manager.get_instance(server_id)
    
    # Pokud už server běží, nechtějte ho startovat znovu
    if instance.process and instance.process.poll() is None:
        return False
    
    try:
        server_process = subprocess.Popen(
            ["java", "-Xmx4G", "-Xms2G", "-jar", paths['server_jar'], "nogui"],
            cwd=paths['server_path'],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Počkej chvíli, než proces naběhne (volitelné, ale užitečné)
        time.sleep(1)

        # Nastav afinitu (jádra 0, 1, 2)

        # Set max capacity based on service level
        if server.service_level == 1:
            CORES_to_add = 2  #2 cores
        elif server.service_level == 2:
            CORES_to_add = 4 #4 cores
        else:  # level 3
            CORES_to_add = 6 #6 cores

        FREE_cores = []
        x = 0

        while len(FREE_cores) < CORES_to_add and x < total_cores:
            if x not in USED_CPU:
                FREE_cores.append(x)
            x += 1

        if len(FREE_cores) < CORES_to_add:
            print("Nedostatek volných jader!")
            # Můžeš zvážit fallback nebo jiné chování
            return False
    
        USED_CPU += FREE_cores
        print(f'všechny použitá jádra {USED_CPU}')
        print(f"počet jader, keré by se měli přiřadit serveru {CORES_to_add}")
        print(f"jádra která se přiřadí novému serveru {FREE_cores}")

        p = psutil.Process(server_process.pid)
        p.cpu_affinity(FREE_cores)

        # save informations on which cores server running
        instance.set_assigned_cores(FREE_cores)

        # Store the process
        instance.process = server_process
        
        # Start reading console output in separate thread
        threading.Thread(
            target=read_console_output, 
            args=(server_id, server_process),
            daemon=True
        ).start()

        return True
    except Exception as e:
        print(f"Start error for server {server_id}: {e}")
        return False
    
def read_console_output(server_id, process):
    """Read console output for a specific server"""
    instance = server_manager.get_instance(server_id)
    
    for line in iter(process.stdout.readline, ''):
        instance.add_output_line(line)
        
        if "Done" in line:  # Server started successfully
            print(f"Server {server_id} started: {line}")

    # Clean up when process ends
    process.stdout.close()
    process.wait()
    instance.process = None

def stop_server(server_id, pid):
    """Stop a specific server"""
    instance = server_manager.get_instance(server_id)
    
    try:
        # Pokud máme proces v našem manageru, použijeme ho
        if instance.process:
            os.kill(instance.process.pid, signal.CTRL_BREAK_EVENT)
        else:
            # Fallback - použijeme poskytnuté PID
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        
        # Wait max 30 seconds for shutdown
        for _ in range(30):
            if not psutil.pid_exists(pid):
                instance.release_cores() #remove cores from global list
                instance.process = None
                return True
            time.sleep(1)
        
        # Forceful termination if still running
        os.kill(pid, signal.SIGTERM)
        instance.release_cores() #remove cores from global list
        instance.process = None
        return True
    except ProcessLookupError:
        instance.release_cores() #remove cores from global list
        instance.process = None
        return True  # Process already stopped
    except Exception as e:
        print(f"Stop error for server {server_id}: {e}")
        return False
    
def restart_server(server_id):
    """Restart a specific server"""
    status = get_server_status(server_id)
    if status['status'] == 'running':
        if not stop_server(server_id, status['pid']):
            return False
        time.sleep(5)
    return start_server(server_id)

def send_command_to_server(server_id, command):
    """Send command to specific server"""
    instance = server_manager.get_instance(server_id)
    
    if not instance.process or instance.process.poll() is not None:
        return False
        
    try:
        instance.process.stdin.write(command + '\n')
        instance.process.stdin.flush()
        return True
    except Exception as e:
        print(f"Command error for server {server_id}: {e}")
        return False

def read_latest_logs(server_id, lines=50):
    """Get latest logs for specific server"""
    instance = server_manager.get_instance(server_id)
    return instance.get_output(lines)


def create_backup_for_server(server_id, backup_name=None):
    """Create backup for specific server"""
    paths = get_server_paths(server_id)
    if not paths:
        return False, "Server not found"
    
    if not backup_name:
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    try:
        # Folders to backup
        worlds_to_backup = ["world", "world_nether", "world_the_end"]
        
        # Backup path
        backup_path = os.path.join(paths['backup_path'], backup_name)
        os.makedirs(backup_path, exist_ok=True)
        
        # Check disk space
        total_size = 0
        for world in worlds_to_backup:
            world_path = os.path.join(paths['server_path'], world)
            if os.path.exists(world_path):
                total_size += get_folder_size(world_path)
        
        free_space = shutil.disk_usage(paths['backup_path']).free
        if free_space < total_size * 1.2:  # 20% buffer
            raise Exception("Not enough disk space for backup")
            
        # Backup each world
        for world in worlds_to_backup:
            world_path = os.path.join(paths['server_path'], world)
            if os.path.exists(world_path):
                shutil.copytree(
                    world_path,
                    os.path.join(backup_path, world),
                    dirs_exist_ok=True
                )
        
        return True, backup_path
    except Exception as e:
        print(f"Backup failed for server {server_id}: {e}")
        return False, str(e)
    
def restore_backup_for_server(server_id, backup_name):
    """Restore backup for specific server"""
    paths = get_server_paths(server_id)
    if not paths:
        return False, "Server not found"
    
    try:
        backup_path = os.path.join(paths['backup_path'], backup_name)
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup {backup_name} doesn't exist")
            
        # Worlds to restore
        worlds_to_restore = ["world", "world_nether", "world_the_end"]
        
        # Restore each world
        for world in worlds_to_restore:
            src_path = os.path.join(backup_path, world)
            dst_path = os.path.join(paths['server_path'], world)
            
            if os.path.exists(src_path):
                # Delete existing world if exists
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                
                # Copy backup
                shutil.copytree(src_path, dst_path)
        
        return True, "All worlds restored successfully"
    except Exception as e:
        return False, str(e)
    
def delete_backup_for_server(server_id, backup_name):
    """Delete backup for specific server"""
    paths = get_server_paths(server_id)
    if not paths:
        return False, "Server not found"
    
    try:
        backup_path = os.path.join(paths['backup_path'], backup_name)
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup {backup_name} doesn't exist")
            
        shutil.rmtree(backup_path)
        return True, "Backup deleted successfully"
    except Exception as e:
        return False, str(e)
    
def get_disk_usage_for_server(server_id):
    """Get disk usage for specific server"""
    server = Server.query.get(server_id)
    if not server:
        return None
        
    paths = get_server_paths(server_id)
    if not paths:
        return None
    
    # Set max capacity based on service level
    if server.service_level == 1:
        MAX_CAPACITY = 20 * 1024**3  # 20 GB
    elif server.service_level == 2:
        MAX_CAPACITY = 30 * 1024**3  # 30 GB
    else:  # level 3
        MAX_CAPACITY = 50 * 1024**3  # 50 GB
    
    # Server folder size
    server_size = get_folder_size(paths['server_path']) if os.path.exists(paths['server_path']) else 0
    
    # Backup folder size
    backup_size = get_folder_size(paths['backup_path']) if os.path.exists(paths['backup_path']) else 0
    
    # Backup count
    backup_count = len([name for name in os.listdir(paths['backup_path']) 
                     if os.path.isdir(os.path.join(paths['backup_path'], name))]) if os.path.exists(paths['backup_path']) else 0
    
    return {
        'server_size': server_size,
        'backup_size': backup_size,
        'total_size': server_size + backup_size,
        'max_capacity': MAX_CAPACITY,
        'backup_count': backup_count,
        'server_percent': (server_size / MAX_CAPACITY * 100) if MAX_CAPACITY > 0 else 0,
        'backup_percent': (backup_size / MAX_CAPACITY * 100) if MAX_CAPACITY > 0 else 0,
        'free_space': MAX_CAPACITY - (server_size + backup_size)
    }


server_api = Blueprint('server_api', __name__)


# API endpoints
@server_api.route('/api/server/status')
@login_required
def server_status_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    status = get_server_status(server_id)
    status['players'] = get_online_players(server_id)
    return jsonify(status)

@server_api.route('/api/server/backups')
@login_required
def server_backups_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    return jsonify(get_backups(server_id))

@server_api.route('/api/server/start', methods=['POST'])
@login_required
def start_server_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    success = start_server(server_id)
    return jsonify({'success': success})

@server_api.route('/api/server/stop', methods=['POST'])
@login_required
def stop_server_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    status = get_server_status(server_id)
    if status['status'] == 'running':
        success = stop_server(server_id, status['pid'])
        return jsonify({'success': success})
    return jsonify({'error': 'Server is not running'}), 400

@server_api.route('/api/server/restart', methods=['POST'])
@login_required
def restart_server_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    status = get_server_status(server_id)
    if status['status'] == 'running':
        stop_success = stop_server(server_id, status['pid'])
        if not stop_success:
            return jsonify({'error': 'Failed to stop server'}), 500
        time.sleep(5)
    
    start_success = start_server(server_id)
    return jsonify({'success': start_success})

@server_api.route('/api/server/logs')
@login_required
def server_logs_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    lines = request.args.get('lines', default=50, type=int)
    return jsonify({"lines": read_latest_logs(server_id, lines)})

@server_api.route('/api/server/command', methods=['POST'])
@login_required
def send_command_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    data = request.get_json()
    command = data.get('command')
    if not command:
        return jsonify({'error': 'Missing command'}), 400
    
    success = send_command_to_server(server_id, command)
    return jsonify({'success': success})


@server_api.route('/api/server/backup/create', methods=['POST'])
@login_required
def create_backup_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    status = get_server_status(server_id)
    if status['status'] == 'running':
        return jsonify({'success': False, 'error': 'Server must be stopped to create backup'}), 400
    
    data = request.get_json()
    backup_name = data.get('name', None)
    success, result = create_backup_for_server(server_id, backup_name)
    if success:
        return jsonify({'success': True, 'backup_path': result})
    return jsonify({'success': False, 'error': result}), 400

@server_api.route('/api/server/backup/restore', methods=['POST'])
@login_required
def restore_backup_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    data = request.get_json()
    backup_name = data.get('name')
    if not backup_name:
        return jsonify({'error': 'Missing backup name'}), 400
    
    status = get_server_status(server_id)
    if status['status'] == 'running':
        return jsonify({'error': 'Server must be stopped to restore backup'}), 400
    
    success, message = restore_backup_for_server(server_id, backup_name)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': message}), 400


@server_api.route('/api/server/backup/delete', methods=['POST'])
@login_required
def delete_backup_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    data = request.get_json()
    backup_name = data.get('name')
    if not backup_name:
        return jsonify({'error': 'Missing backup name'}), 400
    
    success, message = delete_backup_for_server(server_id, backup_name)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': message}), 400

@server_api.route('/api/server/disk-usage')
@login_required
def disk_usage_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    usage = get_disk_usage_for_server(server_id)
    if not usage:
        return jsonify({'error': 'Server not found'}), 404
    return jsonify(usage)

@server_api.route('/api/server/admins', methods=['GET'])
@login_required
def get_server_admins():
    server_id = request.args.get('server_id', type=int)
    server = Server.query.get_or_404(server_id)

    is_owner = server.owner_id == current_user.id
    admins = [{'email': admin.email, 'user_id': admin.id} for admin in server.admins]

    return jsonify({'is_owner': is_owner, 'admins': admins})


@server_api.route('/api/server/admins/add', methods=['POST'])
@login_required
def add_server_admin():
    data = request.get_json()
    email = data.get('email')
    server_id = request.args.get('server_id', type=int)

    server = Server.query.get_or_404(server_id)

    if server.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Nemáš oprávnění přidat admina.'}), 403

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'Uživatel s tímto emailem neexistuje.'}), 404

    if user in server.admins:
        return jsonify({'success': False, 'message': 'Uživatel už je adminem.'}), 400

    server.admins.append(user)
    db.session.commit()

    return jsonify({'success': True})


@server_api.route('/api/server/admins/remove', methods=['POST'])
@login_required
def remove_server_admin():
    data = request.get_json()
    user_id = data.get('user_id')
    server_id = request.args.get('server_id', type=int)

    server = Server.query.get_or_404(server_id)

    if server.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Nemáš oprávnění odstranit admina.'}), 403

    user = User.query.get(user_id)
    if not user or user not in server.admins:
        return jsonify({'success': False, 'message': 'Uživatel není adminem.'}), 400

    server.admins.remove(user)
    db.session.commit()

    return jsonify({'success': True})