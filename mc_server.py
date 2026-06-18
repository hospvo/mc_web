import os
import subprocess
import psutil
import shutil
import secrets
import string
import signal
from datetime import datetime, timedelta
import time
import threading
from flask import Blueprint, request, jsonify, current_app, abort, send_file
from flask_login import login_required, current_user
from models import db, User, Plugin, Server, PluginConfig, PluginUpdateLog, server_plugins, PlayerAccessCode, PlayerServerAccess, PlayerNotice,  Mod, ModPack
from plugin_instaler_modrinth import extract_slug_from_url, get_modrinth_plugin_info, get_download_url, handle_web_request
from port_manager import ensure_ports_open, ensure_ports_closed
import requests
from ansi2html import Ansi2HTMLConverter
import yaml
from mcstatus import JavaServer
from app_config import (
    BASE_BUILD_PATH,
    BASE_MODS_PATH,
    BASE_PLUGIN_PATH,
    BASE_SERVERS_PATH,
    MINECRAFT_JAVA_PATH,
)



# Base directory where all server folders will be stored
JAVA_EXECUTABLE = MINECRAFT_JAVA_PATH or "java"
#BASE_SERVERS_PATH = r"D:\\"
#seznam aktuĂˇlnÄ› vyuĹľitĂ˝ch jader
USED_CPU = []
total_cores = psutil.cpu_count(logical=True)  # fyzickĂˇ jĂˇdra, nebo True pro logickĂˇ



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
        'server_jar': f"server_{server_id}.jar"  # UnikĂˇtnĂ­ nĂˇzev podle server_id
    }


class ServerInstance:
    """TĹ™Ă­da pro sprĂˇvu stavu jednoho serveru"""
    def __init__(self, server_id):
        self.server_id = server_id
        self.process = None               # subprocess.Popen instance
        self.psutil_proc = None           # psutil.Process instance pro monitoring
        self.console_output = []
        self.lock = threading.Lock()      # Pro thread-safe operace
        self.assigned_cores = []
        
    def add_output_line(self, line):
        with self.lock:
            self.console_output.append(line)
            # UdrĹľujeme maximĂˇlnÄ› 1000 Ĺ™ĂˇdkĹŻ vĂ˝stupu
            if len(self.console_output) > 1000:
                self.console_output.pop(0)
    
    def get_output(self, lines=50):
        with self.lock:
            return self.console_output[-lines:] if lines > 0 else self.console_output.copy()
        
    # work with cores
    def set_assigned_cores(self, cores):
        """NastavĂ­ pĹ™iĹ™azenĂˇ jĂˇdra pro tento server"""
        with self.lock:
            self.assigned_cores = cores.copy()

    def get_assigned_cores(self):
        """VrĂˇtĂ­ pĹ™iĹ™azenĂˇ jĂˇdra pro tento server"""
        with self.lock:
            return self.assigned_cores.copy()
        
    def release_cores(self):
        """UvolnĂ­ pĹ™iĹ™azenĂˇ jĂˇdra"""
        with self.lock:
            for core in self.assigned_cores:
                if core in USED_CPU:
                    USED_CPU.remove(core)
            self.assigned_cores = []
            
    def cleanup(self):
        """VyÄŤistĂ­ prostĹ™edky pĹ™i zastavenĂ­ serveru"""
        self.release_cores()
        self.psutil_proc = None
        self.process = None
        
class ServerManager:
    """TĹ™Ă­da pro sprĂˇvu vĹˇech server instancĂ­"""
    def __init__(self):
        self.instances = {}  # {server_id: ServerInstance}
        self.instances_lock = threading.Lock()
    
    def get_instance(self, server_id):
        """ZĂ­skĂˇ instanci serveru, vytvoĹ™Ă­ novou pokud neexistuje"""
        with self.instances_lock:
            if server_id not in self.instances:
                self.instances[server_id] = ServerInstance(server_id)
            return self.instances[server_id]
    
    def remove_instance(self, server_id):
        """OdstranĂ­ instanci serveru"""
        with self.instances_lock:
            if server_id in self.instances:
                del self.instances[server_id]



class PluginManager:
    def __init__(self, external_storage_path=BASE_PLUGIN_PATH):
        self.external_storage = external_storage_path
        self._ensure_directories()
    
    def _ensure_directories(self):
        """ZajistĂ­ existenci potĹ™ebnĂ˝ch adresĂˇĹ™ĹŻ v externĂ­m ĂşloĹľiĹˇti"""
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

            # ZĂ­skĂˇme bezpeÄŤnÄ› project_id a metadata
            project_id = info.get("basic_info", {}).get("slug") or slug
            title = info["basic_info"].get("title") or slug
            version = info["latest_version"].get("version_number") if info.get("latest_version") else "unknown"
            author = info["team"][0]["username"] if info.get("team") else "unknown"
            description = info["basic_info"].get("description") or ""
            categories = "; ".join(info["basic_info"].get("categories", ["unknown"]))
            compatible_with = "; ".join(info["latest_version"].get("game_versions", [])) if info.get("latest_version") else ""

            # Kontrola existence pluginu podle unikĂˇtnĂ­ho identifikĂˇtoru (slug nebo project_id)
            existing_plugin = Plugin.query.filter_by(name=project_id).first()
            if existing_plugin:
                return False, {
                    "type": "plugin_exists",
                    "message": f"Plugin '{title}' jiĹľ existuje v databĂˇzi.",
                    "plugin_id": existing_plugin.id,
                    "plugin_name": existing_plugin.display_name or existing_plugin.name
                }

            # StaĹľenĂ­ souboru s validacĂ­
            if not download_url or not download_url.endswith(".jar"):
                return False, "NeplatnĂˇ URL â€“ oÄŤekĂˇvĂˇn .jar soubor"

            try:
                r = requests.get(download_url, timeout=15, stream=True)
                r.raise_for_status()
            except Exception as e:
                return False, f"Chyba pĹ™i stahovĂˇnĂ­ pluginu: {str(e)}"

            filename = f"{slug}-{version}.jar"
            dest_path = os.path.join(BASE_PLUGIN_PATH, "plugins", "core", filename)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # PĹ™idĂˇnĂ­ pluginu do DB â€“ commit aĹľ po ĂşspÄ›chu instalace na server
            plugin = Plugin(
                name=project_id,
                display_name=title,
                version=version,
                author=author,
                description=description,
                file_path=dest_path,
                category=categories,
                compatible_with=compatible_with,
                download_url=download_url,
                source="modrinth",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(plugin)
            db.session.flush()  # jeĹˇtÄ› necommitujeme

            # Pokus o instalaci na server
            success, message = self.install_plugin_to_server(
                plugin_id=plugin.id,
                server_id=server_id,
                user_id=user_id
            )

            if not success:
                db.session.rollback()
                if os.path.exists(dest_path):
                    os.remove(dest_path)  # uklidĂ­me staĹľenĂ˝ soubor
                return False, message

            db.session.commit()
            return True, f"Plugin '{title}' byl nainstalovĂˇn"

        except Exception as e:
            db.session.rollback()
            return False, f"[CHYBA] {str(e)}"

    
    def install_plugin_to_server(self, plugin_id, server_id, user_id):
        """Nainstaluje plugin na konkrĂ©tnĂ­ server"""
        plugin = Plugin.query.get(plugin_id)
        server = Server.query.get(server_id)

        if not plugin or not server:
            return False, "Plugin or server not found"

        # Kontrola, zda jiĹľ nenĂ­ nainstalovĂˇn
        if server.plugins.filter_by(id=plugin_id).first():
            return False, "Plugin already installed on this server"
        
        try:
            # 1. ZĂ­skat cesty pro server pomocĂ­ get_server_paths
            server_paths = get_server_paths(server_id)
            if not server_paths:
                return False, "Could not determine server paths"

            # 1. ZkopĂ­rovat plugin do sloĹľky serveru
            server_plugins_dir = os.path.join(server_paths['server_path'], "plugins")
            print(f"[DEBUG] CĂ­lovĂˇ sloĹľka pluginu: {server_plugins_dir}")

            os.makedirs(server_plugins_dir, exist_ok=True)

            plugin_filename = os.path.basename(plugin.file_path)
            dest_path = os.path.join(server_plugins_dir, plugin_filename)

            print(f"[DEBUG] KopĂ­rovĂˇnĂ­ souboru:")
            print(f"  Ze: {plugin.file_path}")
            print(f"  Do: {dest_path}")
            print(f"  Soubor existuje? {os.path.exists(plugin.file_path)}")

            if not os.path.exists(plugin.file_path):
                return False, f"Plugin file not found at {plugin.file_path}"

            shutil.copy2(plugin.file_path, dest_path)
            print("[DEBUG] Soubor ĂşspÄ›ĹˇnÄ› zkopĂ­rovĂˇn.")

            # 2. PĹ™idat vztah mezi serverem a pluginem
            db.session.execute(
                server_plugins.insert().values(
                    server_id=server_id,
                    plugin_id=plugin_id,
                    installed_at=datetime.utcnow(),
                    is_active=True
                )
            )

            # 3. ZkopĂ­rovat vĂ˝chozĂ­ konfiguraci (pokud existuje)
            config_folder_name = os.path.splitext(plugin.name)[0]
            default_config_dir = os.path.join(self.external_storage, "configs", config_folder_name)
            print(f"[DEBUG] VĂ˝chozĂ­ konfigurace: {default_config_dir} (existuje: {os.path.exists(default_config_dir)})")
            print(f"  self.external_storage: {self.external_storage}")

            if os.path.exists(default_config_dir):
                server_config_dir = os.path.join(server_plugins_dir, plugin.name)
                shutil.copytree(default_config_dir, server_config_dir, dirs_exist_ok=True)
                print("[DEBUG] VĂ˝chozĂ­ konfigurace ĂşspÄ›ĹˇnÄ› zkopĂ­rovĂˇna.")

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
            print(f"[CHYBA] VĂ˝jimka pĹ™i instalaci pluginu: {e}")
            return False, str(e)

    
    def update_plugin(self, plugin_id, new_file_path, user_id):
        """Aktualizuje plugin ve vĹˇech serverech"""
        plugin = Plugin.query.get(plugin_id)
        if not plugin:
            return False, "Plugin not found"
        
        try:
            # 1. VytvoĹ™it zĂˇlohu
            backup_dir = os.path.join(self.external_storage, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{plugin.name}_{datetime.now().strftime('%Y%m%d')}.jar")
            shutil.copy2(plugin.file_path, backup_path)
            
            old_version = plugin.version
            
            # 2. Aktualizovat soubor pluginu
            shutil.copy2(new_file_path, plugin.file_path)
            
            # 3. Aktualizovat metadata pluginu
            # (zde byste mohli parsovat novou verzi z nĂˇzvu souboru)
            plugin.updated_at = datetime.utcnow()
            
            # 4. Aktualizovat plugin na vĹˇech serverech
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

        # Kontrola, zda je plugin nainstalovĂˇn
        if not server.plugins.filter_by(id=plugin_id).first():
            return False, "Plugin is not installed on this server"

        try:
            # 1. ZĂ­skat cesty pro server
            server_paths = get_server_paths(server_id)
            if not server_paths:
                return False, "Could not determine server paths"

            # 2. Smazat plugin ze sloĹľky serveru
            server_plugins_dir = os.path.join(server_paths['server_path'], "plugins")
            plugin_filename = os.path.basename(plugin.file_path)
            plugin_path = os.path.join(server_plugins_dir, plugin_filename)

            print(f"[DEBUG] OdstraĹovĂˇnĂ­ pluginu: {plugin_path}")
            
            if os.path.exists(plugin_path):
                os.remove(plugin_path)
                print("[DEBUG] Soubor pluginu ĂşspÄ›ĹˇnÄ› odstranÄ›n")
            else:
                print("[DEBUG] Soubor pluginu nebyl nalezen, pokraÄŤovĂˇnĂ­ v odinstalaci")

            # 3. Smazat konfiguraci pluginu (pokud existuje)
            config_folder_name = os.path.splitext(plugin.name)[0]
            server_config_dir = os.path.join(server_plugins_dir, plugin.name)
            
            if os.path.exists(server_config_dir):
                shutil.rmtree(server_config_dir)
                print("[DEBUG] Konfigurace pluginu ĂşspÄ›ĹˇnÄ› odstranÄ›na")

            # 4. Odstranit vztah mezi serverem a pluginem
            db.session.execute(
                server_plugins.delete().where(
                    (server_plugins.c.server_id == server_id) &
                    (server_plugins.c.plugin_id == plugin_id)
                )
            )

            # 5. Smazat zĂˇznam o konfiguraci (pokud existuje)
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
            print(f"[CHYBA] VĂ˝jimka pĹ™i odinstalaci pluginu: {e}")
            return False, str(e)
        
    def check_for_updates(self, plugin_id):
        """Zkontroluje, zda mĂˇ plugin dostupnou novÄ›jĹˇĂ­ verzi (aktuĂˇlnÄ› jen Modrinth)."""
        plugin = Plugin.query.get(plugin_id)
        if not plugin:
            return {"update_available": False, "error": "Plugin not found"}

        if plugin.source != "modrinth" or not plugin.name:
            return {"update_available": False, "error": "Update check not supported for this plugin"}

        try:
            from plugin_instaler_modrinth import get_modrinth_plugin_info

            # pouĹľĂ­vĂˇme slug/project_id uloĹľenĂ˝ v plugin.name
            slug = plugin.name
            info = get_modrinth_plugin_info(slug)

            latest_version = info.get("latest_version", {})
            latest_number = latest_version.get("version_number")

            if latest_number and latest_number != plugin.version:
                return {
                    "update_available": True,
                    "new_version": latest_number,
                    "changelog": latest_version.get("changelog") or ""
                }
            else:
                return {"update_available": False}

        except Exception as e:
            return {"update_available": False, "error": str(e)}


# GlobĂˇlnĂ­ manager pro vĹˇechny servery
server_manager = ServerManager()
plugin_manager = PluginManager()

def get_server_status(server_id):
    """ZĂ­skĂˇ stav a statistiky Minecraft serveru"""
    paths = get_server_paths(server_id)
    if not paths:
        return {'status': 'error', 'message': 'Server not found'}

    jar_name = paths['server_jar']
    server = Server.query.get(server_id)
    if not server:
        return {'status': 'error', 'message': 'Server config not found'}

    # Build type
    build_type = server.build_version.build_type.name.upper() if server.build_version else "VANILLA"

    # Limit CPU podle service levelu
    CPU_max_usage = {
        1: '100 %',
        2: '200 %',
        3: '300 %'
    }.get(server.service_level, '100 %')

    # Funkce pro rozpoznĂˇnĂ­ Forge procesu
    def is_forge_process(proc, jar_name):
        try:
            cmdline = ' '.join(proc.cmdline()) if proc.cmdline() else ''
            return (
                'java' in proc.name().lower()
                and (jar_name in cmdline
                     or 'forge' in cmdline.lower()
                     or any(f.endswith('.jar') and 'forge' in f.lower() for f in proc.cmdline()))
            )
        except Exception:
            return False

    # --- 1) Zkontrolovat nĂˇĹˇ manager ---
    instance = server_manager.get_instance(server_id)
    
    # Kontrola procesu v manageru
    if instance.psutil_proc:
        try:
            proc = instance.psutil_proc
            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                mem = proc.memory_info()
                cpu = proc.cpu_percent(interval=0.1)

                return {
                    'status': 'running',
                    'pid': proc.pid,
                    'ram_used_mb': round(mem.rss / (1024 ** 2)),
                    'cpu_percent': round(cpu, 1) if cpu >= 0.1 else 0.0,
                    'since': datetime.fromtimestamp(proc.create_time()).strftime('%d.%m.%Y %H:%M'),
                    'port': 25565,
                    'cpu_max': CPU_max_usage,
                    'build_type': build_type,
                    'assigned_cores': instance.get_assigned_cores()
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # proces uĹľ nebÄ›ĹľĂ­
            print(f"Proces serveru {server_id} jiĹľ nebÄ›ĹľĂ­, provĂˇdĂ­m cleanup")
            instance.cleanup()

    # Kontrola Popen procesu
    if instance.process and instance.process.poll() is None:
        # Popen proces bÄ›ĹľĂ­, ale psutil proces je None - najdeme ho
        try:
            parent = psutil.Process(instance.process.pid)
            for child in parent.children(recursive=True):
                try:
                    cmdline = ' '.join(child.cmdline())
                    if jar_name in cmdline or 'java' in child.name().lower():
                        instance.psutil_proc = child
                        mem = child.memory_info()
                        cpu = child.cpu_percent(interval=0.1)
                        
                        return {
                            'status': 'running',
                            'pid': child.pid,
                            'ram_used_mb': round(mem.rss / (1024 ** 2)),
                            'cpu_percent': round(cpu, 1) if cpu >= 0.1 else 0.0,
                            'since': datetime.fromtimestamp(child.create_time()).strftime('%d.%m.%Y %H:%M'),
                            'port': 25565,
                            'cpu_max': CPU_max_usage,
                            'build_type': build_type,
                            'assigned_cores': instance.get_assigned_cores()
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Chyba pĹ™i hledĂˇnĂ­ procesu: {e}")

    # --- 2) Fallback: hledat v systĂ©mu podle jar_name ---
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline) if isinstance(cmdline, (list, tuple)) else str(cmdline)

            if (build_type == "FORGE" and is_forge_process(proc, jar_name)) or \
               (build_type != "FORGE" and jar_name in cmdline_str):
                mem = proc.memory_info()
                cpu = proc.cpu_percent(interval=0.1)

                # Aktualizovat instanci s nalezenĂ˝m procesem
                instance.psutil_proc = proc
                
                return {
                    'status': 'running',
                    'pid': proc.pid,
                    'ram_used_mb': round(mem.rss / (1024 ** 2)),
                    'cpu_percent': round(cpu, 1) if cpu >= 0.1 else 0.0,
                    'since': datetime.fromtimestamp(proc.info['create_time']).strftime('%d.%m.%Y %H:%M'),
                    'port': 25565,
                    'cpu_max': CPU_max_usage,
                    'build_type': build_type,
                    'assigned_cores': instance.get_assigned_cores()
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # --- 3) Pokud nic nebÄ›ĹľĂ­ ---
    instance.cleanup()

    return {
        'status': 'stopped',
        'cpu_max': CPU_max_usage,
        'build_type': build_type
    }



def get_online_player_info(server_id):
    """
    VrĂˇtĂ­ informace o hrĂˇÄŤĂ­ch online (poÄŤet + seznam jmen).
    UpĹ™ednostĹuje query, pak ping, pak diagnostiku.
    """
    try:
        server = Server.query.get(server_id)
        if not server:
            print(f"[WARN] Server {server_id} nebyl nalezen v databĂˇzi.")
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
                status = JavaServer(server_ip, server.server_port).status()
                return {
                    "count": status.players.online,
                    "names": [p.name for p in (status.players.sample or [])]
                }
            except Exception as e:
                print(f"[WARN] Ping selhal na portu {server.server_port}: {e}")

        # 3. DiagnostickĂ˝ endpoint (HTTP)
        if server.diagnostic_server_port:
            try:
                url = f"http://localhost:{server.diagnostic_server_port}/players"
                print(f"[INFO] Pokus o dotaz na diagnostickĂ˝ endpoint: {url}")
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "count": data.get("online_players", 0),
                        "names": data.get("player_names", [])
                    }
            except requests.exceptions.RequestException as e:
                print(f"[WARN] Chyba pĹ™i dotazu na diagnostickĂ˝ port: {e}")

        return {"count": 0, "names": []}

    except Exception as e:
        print(f"[ERROR] NeoÄŤekĂˇvanĂˇ chyba pĹ™i zĂ­skĂˇvĂˇnĂ­ hrĂˇÄŤĹŻ pro server {server_id}: {e}")
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
        return False
    upnp_ok, fw_ok = ensure_ports_open(server_id, server.server_port, server.query_port)
    if not (upnp_ok or fw_ok):
        print(f"[WARN] NepodaĹ™ilo se otevĹ™Ă­t porty pro server {server_id}")
    
    build_type = server.build_version.build_type.name.upper() if server.build_version else "VANILLA"
    instance = server_manager.get_instance(server_id)

    # Kontrola, zda jiĹľ server bÄ›ĹľĂ­
    if instance.process and instance.process.poll() is None:
        print(f"Server {server_id} jiĹľ bÄ›ĹľĂ­")
        return False
    
    try:
        # Forge potĹ™ebuje jinĂ© parametry
        if build_type == "FORGE":
            java_args = [
                JAVA_EXECUTABLE, "-Xmx6G", "-Xms3G",
                "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled",
                "-XX:MaxGCPauseMillis=200", "-XX:+UnlockExperimentalVMOptions",
                "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
                "-jar", paths['server_jar'], "nogui"
            ]
        else:
            java_args = [JAVA_EXECUTABLE, "-Xmx4G", "-Xms2G", "-jar", paths['server_jar'], "nogui"]

        # SpuĹˇtÄ›nĂ­ serveru
        process = subprocess.Popen(
            java_args,
            cwd=paths['server_path'],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8'
        )

        time.sleep(2)  # Dej JVM chvilku ÄŤasu

        if process.poll() is not None:
            try:
                early_output = process.stdout.read() if process.stdout else ""
                for line in early_output.splitlines():
                    instance.add_output_line(line.strip())
                    print(line)
            except Exception as output_error:
                print(f"Chyba pĹ™i ÄŤtenĂ­ vĂ˝stupu po pĂˇdu serveru {server_id}: {output_error}")

            instance.cleanup()
            _close_server_ports(server_id)
            print(f"Server {server_id} se nespustil, JVM skonÄŤila s kĂłdem {process.returncode}")
            return False

        # NajĂ­t skuteÄŤnĂ˝ JVM proces
        psutil_proc = None
        try:
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                try:
                    cmdline = ' '.join(child.cmdline())
                    if paths['server_jar'] in cmdline or 'java' in child.name().lower():
                        psutil_proc = child
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Fallback na rodiÄŤovskĂ˝ proces
            if psutil_proc is None:
                psutil_proc = parent
        except Exception as e:
            print(f"Chyba pĹ™i hledĂˇnĂ­ procesu: {e}")
            psutil_proc = psutil.Process(process.pid)

        # NastavenĂ­ afinity (CPU core assignment)
        if server.service_level == 1:
            cores_to_assign = 2
        elif server.service_level == 2:
            cores_to_assign = 4
        else:
            cores_to_assign = 6

        free_cores = []
        for core in range(total_cores):
            if core not in USED_CPU:
                free_cores.append(core)
            if len(free_cores) >= cores_to_assign:
                break

        if len(free_cores) < cores_to_assign:
            print("Nedostatek volnĂ˝ch jader!")
            process.terminate()
            return False
    
        # PĹ™iĹ™azenĂ­ jader
        USED_CPU.extend(free_cores)
        try:
            psutil_proc.cpu_affinity(free_cores)
        except Exception as e:
            print(f"Chyba pĹ™i nastavovĂˇnĂ­ affinity: {e}")

        # UloĹľenĂ­ referencĂ­
        instance.process = process
        instance.psutil_proc = psutil_proc
        instance.set_assigned_cores(free_cores)

        # Start ÄŤtenĂ­ konzole
        threading.Thread(
            target=read_console_output, 
            args=(server_id, process),
            daemon=True
        ).start()

        print(f"Server {server_id} ĂşspÄ›ĹˇnÄ› spuĹˇtÄ›n, pĹ™iĹ™azena jĂˇdra: {free_cores}")
        return True
        
    except Exception as e:
        print(f"Chyba pĹ™i startu serveru {server_id}: {e}")
        # UvolnÄ›nĂ­ jader pĹ™i chybÄ›
        instance.cleanup()
        return False

    
def read_console_output(server_id, process):
    """Read console output for a specific server"""
    instance = server_manager.get_instance(server_id)
    
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                instance.add_output_line(line.strip())
                
                if "Done" in line:  # Server started successfully
                    print(f"Server {server_id} started successfully: {line.strip()}")
    except Exception as e:
        print(f"Chyba pĹ™i ÄŤtenĂ­ konzole serveru {server_id}: {e}")
    finally:
        # Clean up when process ends
        try:
            process.stdout.close()
        except:
            pass
            
        return_code = process.wait()
        print(f"Proces serveru {server_id} skonÄŤil s kĂłdem: {return_code}")
        instance.cleanup()

def stop_server(server_id, pid=None):
    """Stop a specific server and close its ports."""
    instance = server_manager.get_instance(server_id)
    
    try:
        # PrioritnÄ› pouĹľijeme proces z instance
        target_pid = None
        if instance.psutil_proc:
            target_pid = instance.psutil_proc.pid
        elif instance.process and instance.process.poll() is None:
            target_pid = instance.process.pid
        elif pid:
            target_pid = pid
            
        if not target_pid:
            print(f"Nelze najĂ­t PID pro zastavenĂ­ serveru {server_id}")
            instance.cleanup()
            # I kdyĹľ proces nenĂ­ nalezen, zkusĂ­me zavĹ™Ă­t porty (pro jistotu)
            _close_server_ports(server_id)
            return True  # UĹľ je zastavenĂ˝
            
        # Pokus o graceful shutdown
        if instance.process and instance.process.poll() is None:
            try:
                instance.process.stdin.write('stop\n')
                instance.process.stdin.flush()
            except Exception as e:
                print(f"Chyba pĹ™i posĂ­lĂˇnĂ­ stop pĹ™Ă­kazu: {e}")
        
        # Wait max 30 seconds for shutdown
        for _ in range(30):
            if not psutil.pid_exists(target_pid):
                instance.cleanup()
                print(f"Server {server_id} ĂşspÄ›ĹˇnÄ› zastaven")
                _close_server_ports(server_id)
                return True
            time.sleep(1)
        
        # Forceful termination if still running
        print(f"VynucenĂ© ukonÄŤenĂ­ serveru {server_id}")
        try:
            proc = psutil.Process(target_pid)
            proc.terminate()
            proc.wait(timeout=10)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                os.kill(target_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
                
        instance.cleanup()
        _close_server_ports(server_id)
        return True
        
    except Exception as e:
        print(f"Chyba pĹ™i zastavovĂˇnĂ­ serveru {server_id}: {e}")
        instance.cleanup()
        # I pĹ™i chybÄ› se pokusĂ­me zavĹ™Ă­t porty
        _close_server_ports(server_id)
        return False

def _close_server_ports(server_id):
    """PomocnĂˇ funkce pro zavĹ™enĂ­ portĹŻ danĂ©ho serveru."""
    try:
        server = Server.query.get(server_id)
        if server:
            ensure_ports_closed(server.id, server.server_port, server.query_port)
        else:
            print(f"[WARN] Server {server_id} nebyl nalezen pĹ™i zavĂ­rĂˇnĂ­ portĹŻ.")
    except Exception as e:
        print(f"[ERROR] Chyba pĹ™i zavĂ­rĂˇnĂ­ portĹŻ serveru {server_id}: {e}")
    
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


@server_api.route('/api/servers/status')
@login_required
def all_servers_status_api():
    """VrĂˇtĂ­ stavy vĹˇech serverĹŻ uĹľivatele v jednom requestu"""
    user = current_user
    
    # ZĂ­skat vĹˇechny servery uĹľivatele
    owned = user.owned_servers
    admin_only = user.admin_of_servers.filter(Server.owner_id != user.id).all()
    all_servers = list(owned) + admin_only
    
    statuses = {}
    for server in all_servers:
        status = get_server_status(server.id)
        statuses[server.id] = status
    
    return jsonify(statuses)

# API endpoints
@server_api.route('/api/server/status', methods=['GET'])
@login_required
def server_status_api():
    # Podpora pro query parametry i JSON tÄ›lo
    if request.is_json:
        data = request.get_json()
        server_id = data.get('server_id') if data else None
    else:
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


@server_api.route('/api/server/info', methods=['GET'])
@login_required
def get_server_info():
    # Podpora pro query parametry i JSON tÄ›lo
    if request.is_json:
        data = request.get_json()
        server_id = data.get('server_id') if data else None
    else:
        server_id = request.args.get('server_id', type=int)
    
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400

    server = Server.query.get(server_id)
    if not server:
        return jsonify({'error': 'Server not found'}), 404

    return jsonify({
        "server_loader": server.build_version.build_type.name,  # napĹ™. "Paper"
        "mc_version": server.build_version.mc_version,          # napĹ™. "1.20.1"
        "server_port": server.server_port                       # napĹ™. 25565
    })
    


@server_api.route('/api/server/backups', methods=['GET'])
@login_required
def server_backups_api():
    # Podpora pro query parametry i JSON tÄ›lo
    if request.is_json:
        data = request.get_json()
        server_id = data.get('server_id') if data else None
    else:
        server_id = request.args.get('server_id', type=int)
    
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    return jsonify(get_backups(server_id))

@server_api.route('/api/server/start', methods=['POST'])
@login_required
def start_server_api():
    # PĹ™ijĂ­mĂˇme JSON tÄ›lo
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400
    
    server_id = data.get('server_id')
    if not server_id:
        return jsonify({'error': 'Missing server_id in JSON body'}), 400
    
    success = start_server(server_id)
    return jsonify({'success': success})

@server_api.route('/api/server/stop', methods=['POST'])
@login_required
def stop_server_api():
    # PĹ™ijĂ­mĂˇme JSON tÄ›lo
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400
    
    server_id = data.get('server_id')
    if not server_id:
        return jsonify({'error': 'Missing server_id in JSON body'}), 400
    
    status = get_server_status(server_id)
    if status['status'] == 'running':
        success = stop_server(server_id, status['pid'])
        return jsonify({'success': success})
    return jsonify({'error': 'Server is not running'}), 400

@server_api.route('/api/server/restart', methods=['POST'])
@login_required
def restart_server_api():
    # PĹ™ijĂ­mĂˇme JSON tÄ›lo
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400
    
    server_id = data.get('server_id')
    if not server_id:
        return jsonify({'error': 'Missing server_id in JSON body'}), 400
    
    status = get_server_status(server_id)
    if status['status'] == 'running':
        stop_success = stop_server(server_id, status['pid'])
        if not stop_success:
            return jsonify({'error': 'Failed to stop server'}), 500
        time.sleep(5)
    
    start_success = start_server(server_id)
    return jsonify({'success': start_success})

@login_required
@server_api.route('/api/server/logs')
def server_logs_api():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400

    lines = request.args.get('lines', default=50, type=int)
    ansi_lines = read_latest_logs(server_id, lines)  # pĹ™edpoklĂˇdĂˇm, Ĺľe to vracĂ­ list Ĺ™ĂˇdkĹŻ s ANSI kĂłdy

    # SpojĂ­me Ĺ™Ăˇdky do jednoho textu
    ansi_text = "\n".join(ansi_lines)

    conv = Ansi2HTMLConverter(inline=True)
    html_text = conv.convert(ansi_text, full=False)

    return jsonify({"html": html_text})

@server_api.route('/api/server/old-logs')
@login_required
def list_old_logs():
    server_id = request.args.get('server_id')
    paths = get_server_paths(server_id)
    if not paths:
        return jsonify([])

    logs_dir = os.path.join(paths['server_path'], "logs")
    if not os.path.exists(logs_dir):
        return jsonify([])

    logs = sorted(
        [f for f in os.listdir(logs_dir) if f.endswith((".log", ".log.gz"))],
        reverse=True
    )
    return jsonify(logs)


@server_api.route('/api/server/old-logs/view')
@login_required
def view_old_log():
    server_id = request.args.get('server_id')
    filename = request.args.get('filename')
    paths = get_server_paths(server_id)
    if not paths or not filename:
        abort(400)

    log_path = os.path.join(paths['server_path'], "logs", filename)
    if not os.path.exists(log_path):
        abort(404)

    # Pokud je soubor komprimovanĂ˝
    if filename.endswith('.gz'):
        import gzip
        with gzip.open(log_path, 'rt', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    else:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

    return jsonify({"name": filename, "content": content})

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
        return jsonify({'success': False, 'message': 'NemĂˇĹˇ oprĂˇvnÄ›nĂ­ pĹ™idat admina.'}), 403

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'UĹľivatel s tĂ­mto emailem neexistuje.'}), 404

    if user in server.admins:
        return jsonify({'success': False, 'message': 'UĹľivatel uĹľ je adminem.'}), 400

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
        return jsonify({'success': False, 'message': 'NemĂˇĹˇ oprĂˇvnÄ›nĂ­ odstranit admina.'}), 403

    user = User.query.get(user_id)
    if not user or user not in server.admins:
        return jsonify({'success': False, 'message': 'UĹľivatel nenĂ­ adminem.'}), 400

    server.admins.remove(user)
    db.session.commit()

    return jsonify({'success': True})


@server_api.route('/api/server/build-type')
@login_required
def get_server_build_type():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # OvÄ›Ĺ™enĂ­ pĹ™Ă­stupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    build_type = server.build_version.build_type.name if server.build_version else "UNKNOWN"
    
    return jsonify({
        'build_type': build_type,
        'is_mod_server': build_type.upper() in [
            'FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA',
            'JAVA_AGENT', 'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER',
            'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'
        ],
        'is_plugin_server': build_type.upper() in [
            'BUKKIT', 'FOLIA', 'PAPER', 'PURPUR', 'SPIGOT', 'SPONGE'
        ]
    })


### plugin manager ###
@server_api.route('/api/plugins/installed')
@login_required
def get_installed_plugins():
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # OvÄ›Ĺ™enĂ­ pĹ™Ă­stupu
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
            'is_active': True,  # MĹŻĹľete doplnit z M:N tabulky
            'installed_at': None,  # MĹŻĹľete doplnit z M:N tabulky
            'description': plugin.description
        }
        plugins.append(plugin_data)
    
    return jsonify(plugins)

@server_api.route('/api/plugins/available')
@login_required
def get_available_plugins():
    # FiltrovĂˇnĂ­ podle parametrĹŻ
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
    
    # OvÄ›Ĺ™enĂ­ pĹ™Ă­stupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    # Kontrola, zda jiĹľ nenĂ­ nainstalovĂˇn
    if plugin in server.plugins:
        return jsonify({'error': 'Plugin already installed'}), 400
    
    try:
        # Zde byste volali vĂˇĹˇ PluginManager
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
    
    # OvÄ›Ĺ™enĂ­ pĹ™Ă­stupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    # Kontrola, zda je nainstalovĂˇn
    if plugin not in server.plugins:
        return jsonify({'error': 'Plugin not installed on this server'}), 400
    
    try:
        # Zde byste volali vĂˇĹˇ PluginManager pro odinstalaci
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

    # OvÄ›Ĺ™enĂ­ pĹ™Ă­stupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    updates = []
    for plugin in server.plugins:
        update_info = plugin_manager.check_for_updates(plugin.id)
        if update_info.get('update_available'):
            updates.append({
                'plugin_id': plugin.id,
                'name': plugin.display_name or plugin.name,
                'current_version': plugin.version,
                'new_version': update_info.get('new_version'),
                'changelog': update_info.get('changelog', "")
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
        return jsonify({'success': False, 'error': 'ChybĂ­ url'}), 400
    if not download_url:  
        return jsonify({'success': False, 'error': 'ChybĂ­ download_url'}), 400
    if not server_id:
        return jsonify({'success': False, 'error': 'ChybĂ­ server_id'}), 400

    # OvÄ›Ĺ™enĂ­ vlastnictvĂ­ serveru
    server = Server.query.get_or_404(server_id)
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    # VolĂˇnĂ­ funkce pro instalaci
    success, result = plugin_manager.install_plugin_from_modrinth_url(
        url, 
        server_id, 
        current_user.id, 
        download_url  
    )

    if success:
        return jsonify({'success': True, 'message': result})
    else:
        # SpeciĂˇlnĂ­ oĹˇetĹ™enĂ­ pro existujĂ­cĂ­ plugin
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


@server_api.route('/api/server/player-access/generate-code', methods=['POST'])
@login_required
def generate_player_access_code():
    server_id = request.json.get('server_id')
    expires_hours = request.json.get('expires_hours', 24)
    max_uses = request.json.get('max_uses', None)
    
    server = Server.query.get_or_404(server_id)
    
    # OvÄ›Ĺ™enĂ­, Ĺľe uĹľivatel je admin/owner
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    # GenerovĂˇnĂ­ unikĂˇtnĂ­ho kĂłdu
    def generate_code():
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    
    code = generate_code()
    while PlayerAccessCode.query.filter_by(access_code=code).first():
        code = generate_code()
    
    # VytvoĹ™enĂ­ pĹ™Ă­stupovĂ©ho kĂłdu
    access_code = PlayerAccessCode(
        server_id=server_id,
        access_code=code,
        created_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(hours=expires_hours) if expires_hours else None,
        max_uses=max_uses
    )
    
    db.session.add(access_code)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'code': code,
        'expires_at': access_code.expires_at.isoformat() if access_code.expires_at else None,
        'max_uses': max_uses
    })

@server_api.route('/api/server/player-access/codes')
@login_required
def list_player_access_codes():
    server_id = request.args.get('server_id')
    server = Server.query.get_or_404(server_id)
    
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    codes = PlayerAccessCode.query.filter_by(server_id=server_id).order_by(PlayerAccessCode.created_at.desc()).all()
    
    return jsonify([{
        'id': code.id,
        'code': code.access_code,
        'created_at': code.created_at.isoformat(),
        'expires_at': code.expires_at.isoformat() if code.expires_at else None,
        'max_uses': code.max_uses,
        'use_count': code.use_count,
        'is_active': code.is_active and (not code.expires_at or code.expires_at > datetime.utcnow())
    } for code in codes])

@server_api.route('/api/server/player-access/revoke-code', methods=['POST'])
@login_required
def revoke_player_access_code():
    data = request.get_json()
    code_id = data.get('code_id')
    
    if not code_id:
        return jsonify({'success': False, 'error': 'ChybÄ›jĂ­cĂ­ code_id'}), 400
    
    access_code = PlayerAccessCode.query.get(code_id)
    if not access_code:
        return jsonify({'success': False, 'error': 'KĂłd nebyl nalezen'}), 404
    
    server = access_code.server
    
    # OvÄ›Ĺ™enĂ­, Ĺľe uĹľivatel je admin/owner
    if server.owner_id != current_user.id and current_user not in server.admins:
        return jsonify({'success': False, 'error': 'NemĂˇte oprĂˇvnÄ›nĂ­'}), 403
    
    access_code.is_active = False
    db.session.commit()
    
    return jsonify({'success': True})

@server_api.route('/api/player/join-with-code', methods=['POST'])
@login_required
def join_server_with_code():
    access_code_str = request.json.get('access_code')
    
    access_code = PlayerAccessCode.query.filter_by(access_code=access_code_str).first()
    if not access_code:
        return jsonify({'success': False, 'error': 'NeplatnĂ˝ pĹ™Ă­stupovĂ˝ kĂłd'})
    
    # Kontrola platnosti kĂłdu
    if not access_code.is_active:
        return jsonify({'success': False, 'error': 'PĹ™Ă­stupovĂ˝ kĂłd jiĹľ nenĂ­ platnĂ˝'})
    if access_code.expires_at and access_code.expires_at < datetime.utcnow():
        return jsonify({'success': False, 'error': 'PĹ™Ă­stupovĂ˝ kĂłd vyprĹˇel'})
    if access_code.max_uses and access_code.use_count >= access_code.max_uses:
        return jsonify({'success': False, 'error': 'PĹ™Ă­stupovĂ˝ kĂłd byl jiĹľ pouĹľit maximĂˇlnĂ­ poÄŤet krĂˇt'})
    
    server = access_code.server
    
    # Kontrola, zda uĹľivatel uĹľ nenĂ­ vlastnĂ­k nebo admin
    if server.owner_id == current_user.id:
        return jsonify({'success': False, 'error': 'Jste vlastnĂ­kem tohoto serveru â€“ nenĂ­ tĹ™eba se pĹ™ipojovat kĂłdem.'})
    if current_user in server.admins:
        return jsonify({'success': False, 'error': 'JiĹľ jste administrĂˇtorem tohoto serveru.'})
    
    # Kontrola, zda uĹľ nenĂ­ hrĂˇÄŤem
    existing_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=access_code.server_id
    ).first()
    
    if existing_access:
        return jsonify({'success': False, 'error': 'JiĹľ jste pĹ™ipojen k tomuto serveru jako hrĂˇÄŤ.'})
    
    # VytvoĹ™enĂ­ pĹ™Ă­stupu
    player_access = PlayerServerAccess(
        user_id=current_user.id,
        server_id=access_code.server_id,
        access_code_id=access_code.id
    )
    access_code.use_count += 1
    db.session.add(player_access)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'server_name': server.name,
        'server_id': server.id
    })

@server_api.route('/api/server/player-access/check')
@login_required
def check_player_access():
    """Zkontroluje, zda mĂˇ uĹľivatel pĹ™Ă­stup k serveru jako hrĂˇÄŤ"""
    server_id = request.args.get('server_id')
    
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    return jsonify({'has_player_access': has_access})


def is_mod_server(server):
    """Zkontroluje, zda server podporuje mĂłdy"""
    if not server.build_version or not server.build_version.build_type:
        return False
    
    build_type = server.build_version.build_type.name.upper()
    mod_builds = [
        'FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA',
        'JAVA_AGENT', 'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER',
        'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'
    ]
    return build_type in mod_builds




############################ player API

# HrĂˇÄŤskĂ© endpointy - pouze pro servery, ke kterĂ˝m mĂˇ hrĂˇÄŤ pĹ™Ă­stup
@server_api.route('/api/player/server/info')
@login_required
def player_server_info():
    """Informace o serveru pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400

    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403

    server = Server.query.get(server_id)
    if not server:
        return jsonify({'error': 'Server not found'}), 404

    return jsonify({
        "server_loader": server.build_version.build_type.name if server.build_version else "Unknown",
        "mc_version": server.build_version.mc_version if server.build_version else "Unknown",
        "server_port": server.server_port
    })

@server_api.route('/api/player/server/status')
@login_required
def player_server_status():
    """Status serveru pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403
    
    status = get_server_status(server_id)

    if status['status'] == 'running':
        player_info = get_online_player_info(server_id)
        status['players'] = player_info["count"]
        status['player_names'] = player_info["names"]
    else:
        status['players'] = 0
        status['player_names'] = []
    
    return jsonify(status)

@server_api.route('/api/player/notices')
@login_required
def player_notices():
    """OznĂˇmenĂ­ pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'ChybĂ­ server_id'}), 400
    
    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403
    
    # HrĂˇÄŤi vidĂ­ pouze aktivnĂ­ oznĂˇmenĂ­
    notices = PlayerNotice.query.filter_by(
        server_id=server_id, 
        is_active=True
    ).order_by(
        PlayerNotice.is_pinned.desc(),
        PlayerNotice.created_at.desc()
    ).all()
    
    return jsonify([{
        'id': notice.id,
        'title': notice.title,
        'content': notice.content,
        'type': notice.notice_type,
        'is_pinned': notice.is_pinned,
        'author': notice.author.username,
        'created_at': notice.created_at.strftime('%d.%m.%Y %H:%M'),
    } for notice in notices])

@server_api.route('/api/player/mods/installed')
@login_required
def player_installed_mods():
    """NainstalovanĂ© mĂłdy pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400

    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403

    server = Server.query.get_or_404(server_id)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje mĂłdy"}), 400

    mods = []
    for mod in server.mods:
        mods.append({
            "id": mod.id,
            "name": mod.name,
            "display_name": mod.display_name or mod.name,
            "version": mod.version,
            "author": mod.author,
            "description": mod.description,
            "loader": mod.loader,
        })

    return jsonify(mods)

@server_api.route('/api/player/mods/client-pack/download')
@login_required
def player_download_client_pack():
    """StaĹľenĂ­ klientskĂ©ho balĂ­ÄŤku modĹŻ pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400

    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403

    server = Server.query.get_or_404(server_id)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje mĂłdy"}), 400

    # Zde zavolej funkci pro vytvoĹ™enĂ­/stĂˇhnutĂ­ client packu
    # ProzatĂ­m vrĂˇtĂ­me chybu - tuto funkci budeĹˇ muset implementovat
    return jsonify({'error': 'Client pack download not implemented yet'}), 501

@server_api.route('/api/player/modpacks/list')
@login_required
def player_list_modpacks():
    """Seznam modpackĹŻ pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'ChybĂ­ server_id'}), 400
    
    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403
    
    server = Server.query.get_or_404(server_id)
    
    modpacks = ModPack.query.filter_by(server_id=server_id).order_by(ModPack.created_at.desc()).all()
    
    result = []
    for pack in modpacks:
        result.append({
            'id': pack.id,
            'name': pack.name,
            'description': pack.description,
            'author': pack.author.username,
            'created_at': pack.created_at.strftime('%d.%m.%Y %H:%M'),
            'file_size': pack.file_size,
            'download_count': pack.download_count,
            'mod_count': len(pack.mods),
            'mods': [{
                'id': mod.id,
                'name': mod.display_name or mod.name,
                'version': mod.version
            } for mod in pack.mods]
        })
    
    return jsonify(result)

@server_api.route('/api/player/modpacks/download/<int:pack_id>')
@login_required
def player_download_modpack(pack_id):
    """StaĹľenĂ­ modpacku pro hrĂˇÄŤe"""
    modpack = ModPack.query.get_or_404(pack_id)
    server = modpack.server
    
    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server.id
    ).first() is not None
    
    if not has_access:
        abort(403)
    
    if not os.path.exists(modpack.file_path):
        return jsonify({'error': 'Soubor modpacku nebyl nalezen'}), 404
    
    # Inkrementovat poÄŤĂ­tadlo staĹľenĂ­
    modpack.download_count += 1
    db.session.commit()
    
    # Odeslat soubor
    safe_filename = f"{modpack.name.replace(' ', '_')}.zip"
    return send_file(
        modpack.file_path,
        as_attachment=True,
        download_name=safe_filename,
        conditional=True
    )


@server_api.route('/api/player/server/build-type')
@login_required
def player_server_build_type():
    """Typ buildu serveru pro hrĂˇÄŤe"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Missing server_id'}), 400
    
    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'error': 'No access to this server'}), 403
    
    server = Server.query.get_or_404(server_id)
    
    build_type = server.build_version.build_type.name if server.build_version else "UNKNOWN"
    
    return jsonify({
        'build_type': build_type,
        'is_mod_server': is_mod_server(server)
    })

@server_api.route('/api/player/report', methods=['POST'])
@login_required
def player_report():
    """OdeslĂˇnĂ­ nahlĂˇĹˇenĂ­ od hrĂˇÄŤe"""
    data = request.get_json()
    server_id = data.get('server_id')
    message = data.get('message')
    
    if not server_id or not message:
        return jsonify({'success': False, 'error': 'ChybĂ­ povinnĂ© Ăşdaje'}), 400
    
    # Kontrola pĹ™Ă­stupu hrĂˇÄŤe
    has_access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first() is not None
    
    if not has_access:
        return jsonify({'success': False, 'error': 'No access to this server'}), 403
    
    try:
        # Zde mĹŻĹľeĹˇ implementovat odeslĂˇnĂ­ nahlĂˇĹˇenĂ­ (email, notifikace, uloĹľenĂ­ do DB)
        # ProzatĂ­m vrĂˇtĂ­me success
        print(f"NahlĂˇĹˇenĂ­ od hrĂˇÄŤe {current_user.username} pro server {server_id}: {message}")
        
        return jsonify({
            'success': True, 
            'message': 'NahlĂˇĹˇenĂ­ bylo ĂşspÄ›ĹˇnÄ› odeslĂˇno administrĂˇtorĹŻm'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
