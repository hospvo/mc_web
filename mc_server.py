import os
import subprocess
import psutil
import shutil
import signal
from datetime import datetime
import time
import threading
from flask import Blueprint, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from models import db, User, Plugin, Server, PluginConfig, PluginUpdateLog, server_plugins
from plugin_instaler_modrinth import extract_slug_from_url, get_modrinth_plugin_info, get_download_url, handle_web_request
import requests
from ansi2html import Ansi2HTMLConverter
import yaml
from mcstatus import JavaServer


# Base directory where all server folders will be stored
BASE_SERVERS_PATH = r"C:\Users\hospv\Documents"
BASE_PLUGIN_PATH = r"C:\Users\hospv\Documents\minecraft_plugins"
BASE_BUILD_PATH = r"C:\Users\hospv\Documents\minecraft_builds"
#BASE_SERVERS_PATH = r"D:\\"
#seznam aktuálně využitých jader
USED_CPU = []
total_cores = psutil.cpu_count(logical=True)  # fyzická jádra, nebo True pro logická



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



class PluginManager:
    def __init__(self, external_storage_path=BASE_PLUGIN_PATH):
        self.external_storage = external_storage_path
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Zajistí existenci potřebných adresářů v externím úložišti"""
        dirs = [
            'plugins/core',
            'plugins/optional',
            'plugins/deprecated',
            'configs',
            'backups',
            'temp'
        ]
        
        for dir_path in dirs:
            full_path = os.path.join(self.external_storage, dir_path)
            os.makedirs(full_path, exist_ok=True)

    def install_plugin_from_modrinth_url(self, url, server_id, user_id, download_url):
        try:
            slug = extract_slug_from_url(url)
            info = get_modrinth_plugin_info(slug)
            #download_url = get_download_url(url)

            # Získání hlavních informací z API
            title = info["basic_info"]["title"] or slug
            version = info["latest_version"]["version_number"] or "unknown"
            author = (info["team"][0]["username"] if info["team"] else "unknown")
            description = info["basic_info"]["description"] or ""
            category = "; ".join(info["basic_info"].get("categories", ["unknown"]))

            # Kontrola existence v DB
            existing_plugin = Plugin.query.filter_by(name=slug).first()
            if existing_plugin:
                # Vrátíme speciální status kód 409 Conflict
                return False, {
                    "type": "plugin_exists",
                    "message": f"Plugin '{title}' již existuje v databázi.",
                    "plugin_id": existing_plugin.id,
                    "plugin_name": existing_plugin.display_name
                }

            # Stažení .jar do správné složky
            filename = f"{slug}-{version}.jar"
            dest_path = os.path.join(BASE_PLUGIN_PATH, "plugins", "core", filename)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            r = requests.get(download_url)
            if r.status_code != 200:
                return False, "Chyba při stahování pluginu"
            with open(dest_path, "wb") as f:
                f.write(r.content)

            # Vytvoření záznamu v DB
            plugin = Plugin(
                name=slug,
                display_name=title,
                version=version,
                author=author,
                description=description,
                file_path=dest_path,
                category=category,
                compatible_with="; ".join(info["latest_version"].get("game_versions", [])),
                download_url=download_url,
                source="modrinth",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(plugin)
            db.session.commit()

            # Instalace na server
            success, message = plugin_manager.install_plugin_to_server(
                plugin_id=plugin.id,
                server_id=server_id,
                user_id=user_id
            )
            return success, message

        except Exception as e:
            db.session.rollback()
            return False, f"[CHYBA] {str(e)}"
    
    def install_plugin_to_server(self, plugin_id, server_id, user_id):
        """Nainstaluje plugin na konkrétní server"""
        plugin = Plugin.query.get(plugin_id)
        server = Server.query.get(server_id)

        if not plugin or not server:
            return False, "Plugin or server not found"

        # Kontrola, zda již není nainstalován
        if server.plugins.filter_by(id=plugin_id).first():
            return False, "Plugin already installed on this server"
        
        try:
            # 1. Získat cesty pro server pomocí get_server_paths
            server_paths = get_server_paths(server_id)
            if not server_paths:
                return False, "Could not determine server paths"

            # 1. Zkopírovat plugin do složky serveru
            server_plugins_dir = os.path.join(server_paths['server_path'], "plugins")
            print(f"[DEBUG] Cílová složka pluginu: {server_plugins_dir}")

            os.makedirs(server_plugins_dir, exist_ok=True)

            plugin_filename = os.path.basename(plugin.file_path)
            dest_path = os.path.join(server_plugins_dir, plugin_filename)

            print(f"[DEBUG] Kopírování souboru:")
            print(f"  Ze: {plugin.file_path}")
            print(f"  Do: {dest_path}")
            print(f"  Soubor existuje? {os.path.exists(plugin.file_path)}")

            if not os.path.exists(plugin.file_path):
                return False, f"Plugin file not found at {plugin.file_path}"

            shutil.copy2(plugin.file_path, dest_path)
            print("[DEBUG] Soubor úspěšně zkopírován.")

            # 2. Přidat vztah mezi serverem a pluginem
            db.session.execute(
                server_plugins.insert().values(
                    server_id=server_id,
                    plugin_id=plugin_id,
                    installed_at=datetime.utcnow(),
                    is_active=True
                )
            )

            # 3. Zkopírovat výchozí konfiguraci (pokud existuje)
            config_folder_name = os.path.splitext(plugin.name)[0]
            default_config_dir = os.path.join(self.external_storage, "configs", config_folder_name)
            print(f"[DEBUG] Výchozí konfigurace: {default_config_dir} (existuje: {os.path.exists(default_config_dir)})")
            print(f"  self.external_storage: {self.external_storage}")

            if os.path.exists(default_config_dir):
                server_config_dir = os.path.join(server_plugins_dir, plugin.name)
                shutil.copytree(default_config_dir, server_config_dir, dirs_exist_ok=True)
                print("[DEBUG] Výchozí konfigurace úspěšně zkopírována.")

                server_config = PluginConfig(
                    plugin_id=plugin_id,
                    server_id=server_id,
                    config_path=server_config_dir,
                    last_updated=datetime.utcnow()
                )
                db.session.add(server_config)

            # 4. Zaznamenat do logu
            log_entry = PluginUpdateLog(
                plugin_id=plugin_id,
                user_id=user_id,
                action="install",
                version_to=plugin.version,
                notes=f"Installed to server {server.name}"
            )
            db.session.add(log_entry)

            db.session.commit()
            return True, "Plugin installed successfully"

        except Exception as e:
            db.session.rollback()
            print(f"[CHYBA] Výjimka při instalaci pluginu: {e}")
            return False, str(e)

    
    def update_plugin(self, plugin_id, new_file_path, user_id):
        """Aktualizuje plugin ve všech serverech"""
        plugin = Plugin.query.get(plugin_id)
        if not plugin:
            return False, "Plugin not found"
        
        try:
            # 1. Vytvořit zálohu
            backup_dir = os.path.join(self.external_storage, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{plugin.name}_{datetime.now().strftime('%Y%m%d')}.jar")
            shutil.copy2(plugin.file_path, backup_path)
            
            old_version = plugin.version
            
            # 2. Aktualizovat soubor pluginu
            shutil.copy2(new_file_path, plugin.file_path)
            
            # 3. Aktualizovat metadata pluginu
            # (zde byste mohli parsovat novou verzi z názvu souboru)
            plugin.updated_at = datetime.utcnow()
            
            # 4. Aktualizovat plugin na všech serverech
            for server in plugin.servers:
                server_plugins_dir = os.path.join(BASE_PLUGIN_PATH, server.name, "plugins")
                plugin_filename = os.path.basename(plugin.file_path)
                dest_path = os.path.join(server_plugins_dir, plugin_filename)
                
                shutil.copy2(new_file_path, dest_path)
                
                # Zaznamenat aktualizaci
                log_entry = PluginUpdateLog(
                    plugin_id=plugin_id,
                    user_id=user_id,
                    action="update",
                    version_from=old_version,
                    version_to=plugin.version,
                    notes=f"Updated on server {server.name}"
                )
                db.session.add(log_entry)
            
            db.session.commit()
            return True, "Plugin updated on all servers"
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)
        
    def uninstall_plugin(self, plugin_id, server_id, user_id):
        """Odinstaluje plugin ze serveru"""
        plugin = Plugin.query.get(plugin_id)
        server = Server.query.get(server_id)

        if not plugin or not server:
            return False, "Plugin or server not found"

        # Kontrola, zda je plugin nainstalován
        if not server.plugins.filter_by(id=plugin_id).first():
            return False, "Plugin is not installed on this server"

        try:
            # 1. Získat cesty pro server
            server_paths = get_server_paths(server_id)
            if not server_paths:
                return False, "Could not determine server paths"

            # 2. Smazat plugin ze složky serveru
            server_plugins_dir = os.path.join(server_paths['server_path'], "plugins")
            plugin_filename = os.path.basename(plugin.file_path)
            plugin_path = os.path.join(server_plugins_dir, plugin_filename)

            print(f"[DEBUG] Odstraňování pluginu: {plugin_path}")
            
            if os.path.exists(plugin_path):
                os.remove(plugin_path)
                print("[DEBUG] Soubor pluginu úspěšně odstraněn")
            else:
                print("[DEBUG] Soubor pluginu nebyl nalezen, pokračování v odinstalaci")

            # 3. Smazat konfiguraci pluginu (pokud existuje)
            config_folder_name = os.path.splitext(plugin.name)[0]
            server_config_dir = os.path.join(server_plugins_dir, plugin.name)
            
            if os.path.exists(server_config_dir):
                shutil.rmtree(server_config_dir)
                print("[DEBUG] Konfigurace pluginu úspěšně odstraněna")

            # 4. Odstranit vztah mezi serverem a pluginem
            db.session.execute(
                server_plugins.delete().where(
                    (server_plugins.c.server_id == server_id) &
                    (server_plugins.c.plugin_id == plugin_id)
                )
            )

            # 5. Smazat záznam o konfiguraci (pokud existuje)
            config = PluginConfig.query.filter_by(
                plugin_id=plugin_id,
                server_id=server_id
            ).first()
            
            if config:
                db.session.delete(config)

            # 6. Zaznamenat do logu
            log_entry = PluginUpdateLog(
                plugin_id=plugin_id,
                user_id=user_id,
                action="uninstall",
                version_from=plugin.version,
                notes=f"Uninstalled from server {server.name}"
            )
            db.session.add(log_entry)

            db.session.commit()
            return True, "Plugin uninstalled successfully"

        except Exception as e:
            db.session.rollback()
            print(f"[CHYBA] Výjimka při odinstalaci pluginu: {e}")
            return False, str(e)

# Globální manager pro všechny servery
server_manager = ServerManager()
plugin_manager = PluginManager()



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


def get_online_player_info(server_id):
    """
    Vrátí informace o hráčích online (počet + seznam jmen).
    Upřednostňuje query, pak ping, pak diagnostiku.
    """
    try:
        server = Server.query.get(server_id)
        if not server:
            print(f"[WARN] Server {server_id} nebyl nalezen v databázi.")
            return {"count": 0, "names": []}

        server_ip = "localhost"

        # 1. Query (UDP)
        if server.query_port:
            try:
                query = JavaServer(server_ip, server.query_port).query()
                return {
                    "count": query.players.online,
                    "names": query.players.names or []
                }
            except Exception as e:
                print(f"[WARN] Query selhalo na portu {server.query_port}: {e}")

        # 2. Status (TCP ping)
        if server.server_port:
            try:
<<<<<<< Updated upstream
                status = JavaServer(server_ip, server.server_port).status()
                return {
                    "count": status.players.online,
                    "names": [p.name for p in (status.players.sample or [])]
                }
=======
                print(f"[INFO] Pokus o ping na {server_ip}:{server.server_port}")
                server_status = JavaServer(server_ip, server.server_port).status()
                return server_status.players.online
>>>>>>> Stashed changes
            except Exception as e:
                print(f"[WARN] Ping selhal na portu {server.server_port}: {e}")

        # 3. Diagnostický endpoint (HTTP)
        if server.diagnostic_server_port:
            try:
                url = f"http://localhost:{server.diagnostic_server_port}/players"
                print(f"[INFO] Pokus o dotaz na diagnostický endpoint: {url}")
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "count": data.get("online_players", 0),
                        "names": data.get("player_names", [])
                    }
            except requests.exceptions.RequestException as e:
                print(f"[WARN] Chyba při dotazu na diagnostický port: {e}")

        return {"count": 0, "names": []}

    except Exception as e:
        print(f"[ERROR] Neočekávaná chyba při získávání hráčů pro server {server_id}: {e}")
        return {"count": 0, "names": []}

#these two from old methods
def get_online_players(server_id):
    return get_online_player_info(server_id)["count"]

def get_online_player_names(server_id):
    return get_online_player_info(server_id)["names"]


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

    if status['status'] == 'running':
        player_info = get_online_player_info(server_id)
        status['players'] = player_info["count"]
        status['player_names'] = player_info["names"]
    else:
        status['players'] = 0
        status['player_names'] = []
    
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
def server_logs_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400

    lines = request.args.get('lines', default=50, type=int)
    ansi_lines = read_latest_logs(server_id, lines)  # předpokládám, že to vrací list řádků s ANSI kódy

    # Spojíme řádky do jednoho textu
    ansi_text = "\n".join(ansi_lines)

    conv = Ansi2HTMLConverter(inline=True)
    html_text = conv.convert(ansi_text, full=False)

    return jsonify({"html": html_text})

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


### plugin manager ###
@server_api.route('/api/plugins/installed')
@login_required
def get_installed_plugins():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    plugins = []
    for plugin in server.plugins:
        plugin_data = {
            'id': plugin.id,
            'name': plugin.name,
            'display_name': plugin.display_name or plugin.name,
            'version': plugin.version,
            'author': plugin.author,
            'is_active': True,  # Můžete doplnit z M:N tabulky
            'installed_at': None,  # Můžete doplnit z M:N tabulky
            'description': plugin.description
        }
        plugins.append(plugin_data)
    
    return jsonify(plugins)

@server_api.route('/api/plugins/available')
@login_required
def get_available_plugins():
    # Filtrování podle parametrů
    search = request.args.get('search', '').lower()
    category = request.args.get('category', 'all')
    
    query = Plugin.query
    
    if search:
        query = query.filter(db.or_(
            Plugin.name.ilike(f'%{search}%'),
            Plugin.display_name.ilike(f'%{search}%'),
            Plugin.description.ilike(f'%{search}%')
        ))
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    plugins = query.all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'display_name': p.display_name or p.name,
        'version': p.version,
        'author': p.author,
        'description': p.description,
        'category': p.category,
        'compatible_with': p.compatible_with
    } for p in plugins])

@server_api.route('/api/plugins/install', methods=['POST'])
@login_required
def install_plugin():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    plugin_id = request.json.get('plugin_id')
    if not plugin_id:
        return jsonify({'error': 'Missing plugin_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    plugin = Plugin.query.get_or_404(plugin_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    # Kontrola, zda již není nainstalován
    if plugin in server.plugins:
        return jsonify({'error': 'Plugin already installed'}), 400
    
    try:
        # Zde byste volali váš PluginManager
        success, message = plugin_manager.install_plugin_to_server(
            plugin_id=plugin.id,
            server_id=server.id,
            user_id=current_user.id
        )
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@server_api.route('/api/plugins/uninstall', methods=['POST'])
@login_required
def uninstall_plugin():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    plugin_id = request.json.get('plugin_id')
    if not plugin_id:
        return jsonify({'error': 'Missing plugin_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    plugin = Plugin.query.get_or_404(plugin_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    # Kontrola, zda je nainstalován
    if plugin not in server.plugins:
        return jsonify({'error': 'Plugin not installed on this server'}), 400
    
    try:
        # Zde byste volali váš PluginManager pro odinstalaci
        success, message = plugin_manager.uninstall_plugin(
            plugin_id=plugin.id,
            server_id=server.id,
            user_id=current_user.id
        )
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@server_api.route('/api/plugins/check-updates')
@login_required
def check_plugin_updates():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    # Zde byste implementovali kontrolu aktualizací
    # Toto je zjednodušený příklad
    updates = []
    for plugin in server.plugins:
        # Předpokládáme, že máte nějakou metodu pro kontrolu aktualizací
        update_info = plugin_manager.check_for_updates(plugin.id)
        if update_info['update_available']:
            updates.append({
                'plugin_id': plugin.id,
                'name': plugin.name,
                'current_version': plugin.version,
                'new_version': update_info['new_version'],
                'changelog': update_info['changelog']
            })
    
    return jsonify(updates)

@server_api.route('/api/plugins/install-from-url', methods=['POST'])
@login_required
def install_plugin_from_url():
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    url = data.get('url')
    download_url = data.get('download_url')  
    server_id = data.get('server_id')
    plugin_name = data.get('plugin_name')  
    
    if not url:
        return jsonify({'success': False, 'error': 'Chybí url'}), 400
    if not download_url:  
        return jsonify({'success': False, 'error': 'Chybí download_url'}), 400
    if not server_id:
        return jsonify({'success': False, 'error': 'Chybí server_id'}), 400

    # Ověření vlastnictví serveru
    server = Server.query.get_or_404(server_id)
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    # Volání funkce pro instalaci
    success, result = plugin_manager.install_plugin_from_modrinth_url(
        url, 
        server_id, 
        current_user.id, 
        download_url  
    )

    if success:
        return jsonify({'success': True, 'message': result})
    else:
        # Speciální ošetření pro existující plugin
        if isinstance(result, dict) and result.get("type") == "plugin_exists":
            return jsonify({
                'success': False,
                'error': result["message"],
                'plugin_exists': True,
                'plugin_id': result["plugin_id"],
                'plugin_name': result["plugin_name"]
            }), 409  # HTTP 409 Conflict
        else:
            return jsonify({
                'success': False,
                'error': result["message"] if isinstance(result, dict) else result
            }), 400
        
@server_api.route("/api/plugins/get-download-info", methods=["POST"])
def get_plugin_download_info():
    data = request.get_json()
    url = data.get("url")
    server_id = data.get("server_id")
    return jsonify(handle_web_request(url, server_id))