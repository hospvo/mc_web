import os
import shutil
import requests
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, abort, send_file, after_this_request
from flask_login import login_required, current_user
from urllib.parse import urlparse
import tempfile
import zipfile

from models import db, Server, Mod, ModConfig, ModUpdateLog, server_mods, ModPack, mod_pack_mods
from mc_server import BASE_MODS_PATH, BASE_SERVERS_PATH

# Blueprint
BASE_MODPACKS_PATH = "data/modpacks"
mods_api = Blueprint("mods_api", __name__)

def is_mod_server(server: Server) -> bool:
    """Ověří, že server podporuje módy"""
    if not server.build_version or not server.build_version.build_type:
        return False
    
    build_type = server.build_version.build_type.name.upper()
    mod_builds = [
        'FABRIC', 'FORGE', 'NEOFORGE', 'QUILT', 'BABRIC', 'BTA',
        'JAVA_AGENT', 'LEGACY_FABRIC', 'LITELOADER', 'MODLOADER',
        'NILLOADER', 'ORNITHE', 'RIFT', 'RISUGAMI'
    ]
    return build_type in mod_builds

def get_server_loader(server: Server) -> str:
    """Vrátí loader serveru v lowercase (fabric, forge, neoforge, etc.)"""
    if not server.build_version or not server.build_version.build_type:
        return None
    return server.build_version.build_type.name.lower()

# ---- Pomocné funkce pro Modrinth ----

def extract_modrinth_slug(url):
    """Vrátí slug z URL typu https://modrinth.com/mod/<slug> nebo /plugin/<slug>"""
    try:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        
        if len(parts) < 2:
            raise ValueError("Neplatná Modrinth URL - očekáváno https://modrinth.com/mod/<nazev> nebo /plugin/<nazev>")
        
        project_type = parts[0]  # 'mod' nebo 'plugin'
        slug = parts[1]
        
        valid_types = ['mod', 'plugin', 'resourcepack', 'datapack', 'modpack', 'shader']
        if project_type not in valid_types:
            raise ValueError(f"Neplatný typ projektu Modrinth: {project_type}. Očekáváno: {', '.join(valid_types)}")
        
        return slug, project_type
        
    except Exception as e:
        raise ValueError(f"Chyba při parsování URL: {e}")

def get_modrinth_info(slug):
    """Vrátí detailní info o projektu z Modrinthu - funguje pro mody i pluginy."""
    try:
        headers = {
            'User-Agent': 'MinecraftServerManager/1.0 (https://github.com/your-repo)',
            'Accept': 'application/json'
        }
        
        # 1️⃣ Získáme základní info o projektu
        project_url = f"https://api.modrinth.com/v2/project/{slug}"
        project_response = requests.get(project_url, headers=headers, timeout=10)
        
        if project_response.status_code == 404:
            raise ValueError(f"Projekt '{slug}' nebyl nalezen na Modrinth")
        elif project_response.status_code != 200:
            raise ValueError(f"Modrinth API vrátilo chybu: {project_response.status_code}")
            
        project = project_response.json()
        
        # 2️⃣ Získáme verze projektu
        versions_url = f"https://api.modrinth.com/v2/project/{slug}/version"
        versions_response = requests.get(versions_url, headers=headers, timeout=10)
        if versions_response.status_code != 200:
            raise ValueError(f"Chyba při načítání verzí: {versions_response.status_code}")
        versions = versions_response.json()
        
        # 3️⃣ Získáme informace o týmu
        team_url = f"https://api.modrinth.com/v2/project/{slug}/members"
        team_response = requests.get(team_url, headers=headers, timeout=10)
        team = team_response.json() if team_response.status_code == 200 else []

        # 4️⃣ Načteme typ projektu + client/server side metadata
        project_type = project.get("project_type", "mod")
        client_side = project.get("client_side", "optional")   # <- přidáno
        server_side = project.get("server_side", "required")   # <- přidáno

        # 5️⃣ Detekce plugin kompatibility
        can_be_plugin = False
        all_loaders = set()
        plugin_loaders = {'bukkit', 'spigot', 'paper', 'purpur', 'folia', 'sponge'}
        
        for version in versions:
            version_loaders = version.get("loaders", [])
            all_loaders.update(version_loaders)
            if any(loader in plugin_loaders for loader in version_loaders):
                can_be_plugin = True

        # 6️⃣ Vrátíme rozšířené informace
        return {
            "project": project,
            "versions": versions,
            "team": team,
            "project_type": project_type,
            "can_be_plugin": can_be_plugin,
            "all_loaders": list(all_loaders),
            "client_side": client_side,    # <- nové pole
            "server_side": server_side     # <- nové pole
        }
        
    except requests.exceptions.Timeout:
        raise ValueError("Timeout při komunikaci s Modrinth API")
    except requests.exceptions.ConnectionError:
        raise ValueError("Chyba připojení k Modrinth API")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Chyba HTTP: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Neplatná odpověď z Modrinth API: {e}")
    except Exception as e:
        raise ValueError(f"Neočekávaná chyba: {e}")


def pick_best_version(versions, preferred_loader=None, preferred_mc_version=None):
    """Vybere nejlepší verzi modu podle loaderu a MC verze."""
    if not versions:
        return None
    
    # 1. Přesná shoda - loader i MC verze
    for version in versions:
        loaders = version.get("loaders", [])
        mc_versions = version.get("game_versions", [])
        if (preferred_loader and preferred_loader in loaders and 
            preferred_mc_version and preferred_mc_version in mc_versions):
            return version
    
    # 2. Shoda podle loaderu
    for version in versions:
        loaders = version.get("loaders", [])
        if preferred_loader and preferred_loader in loaders:
            return version
    
    # 3. Shoda podle MC verze
    for version in versions:
        mc_versions = version.get("game_versions", [])
        if preferred_mc_version and preferred_mc_version in mc_versions:
            return version
    
    # 4. Nejnovější verze (podle data publikování)
    try:
        return sorted(versions, key=lambda v: v.get("date_published", ""), reverse=True)[0]
    except:
        return versions[0] if versions else None

@mods_api.route("/api/mods/installed")
@login_required
def get_installed_mods():
    server_id = request.args.get("server_id", type=int)
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    server = Server.query.get_or_404(server_id)

    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje módy"}), 400

    mods = []
    for mod in server.mods:
        mods.append({
            "id": mod.id,
            "name": mod.name,
            "display_name": mod.display_name or mod.name,
            "version": mod.version,
            "author": mod.author,
            "is_active": True,
            "installed_at": None,
            "description": mod.description,
            "loader": mod.loader,
            "minecraft_version": mod.minecraft_version
        })

    return jsonify(mods)

@mods_api.route("/api/mods/available")
@login_required
def get_available_mods():
    search = request.args.get("search", "").lower()
    category = request.args.get("category", "all")
    server_id = request.args.get("server_id", type=int)

    # POVINNÉ - musíme mít server_id pro filtrování
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    server = Server.query.get_or_404(server_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje módy"}), 400

    server_loader = get_server_loader(server)
    server_mc_version = server.build_version.mc_version if server.build_version else None

    query = Mod.query

    if search:
        query = query.filter(db.or_(
            Mod.name.ilike(f"%{search}%"),
            Mod.display_name.ilike(f"%{search}%"),
            Mod.description.ilike(f"%{search}%")
        ))

    if category != "all":
        query = query.filter_by(category=category)

    all_mods = query.all()
    
    # FILTROVÁNÍ pouze kompatibilních projektů (modů i pluginů s mod loader support)
    compatible_mods = []
    for mod in all_mods:
        # Pokud mod nemá metadata, přeskočíme ho
        if not mod.supported_loaders or not mod.minecraft_versions:
            continue
            
        try:
            supported_loaders = json.loads(mod.supported_loaders) if mod.supported_loaders else []
            supported_mc_versions = json.loads(mod.minecraft_versions) if mod.minecraft_versions else []
            
            # Kontrola kompatibility - mod musí podporovat loader serveru
            loader_compatible = server_loader in supported_loaders
            
            # Kontrola kompatibility MC verze
            mc_compatible = not server_mc_version or server_mc_version in supported_mc_versions
            
            # ROZŠÍŘENÍ: Projekty, které projdou oběma kontrolami, jsou kompatibilní
            if loader_compatible and mc_compatible:
                compatible_mods.append(mod)
                
        except json.JSONDecodeError:
            # Pokud JSON není validní, přeskočíme mod
            continue

    # Vrátíme seznam kompatibilních projektů s rozšířenými metadaty
    return jsonify([{
        "id": m.id,
        "name": m.name,
        "display_name": m.display_name or m.name,
        "version": m.version,
        "author": m.author,
        "description": m.description,
        "category": m.category,
        "loader": m.loader,
        "minecraft_version": m.minecraft_version,
        "supported_loaders": json.loads(m.supported_loaders) if m.supported_loaders else [],
        "minecraft_versions": json.loads(m.minecraft_versions) if m.minecraft_versions else [],
        # NOVÁ ROZŠÍŘENÍ PRO HYBRIDNÍ PROJEKTY:
        "project_type": m.project_type or "mod",  # mod, plugin, resourcepack, etc.
        "can_be_plugin": m.can_be_plugin if m.can_be_plugin is not None else False,
        "is_hybrid": m.can_be_plugin and (m.project_type == "plugin" or m.project_type is None),
        "icon_url": f"https://cdn.modrinth.com/data/{m.name}/icon.png" if m.source == "modrinth" else None
    } for m in compatible_mods])

@mods_api.route("/api/mods/install", methods=["POST"])
@login_required
def install_mod():
    server_id = request.args.get("server_id", type=int)
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    mod_id = request.json.get("mod_id")
    if not mod_id:
        return jsonify({"error": "Missing mod_id"}), 400

    server = Server.query.get_or_404(server_id)
    mod = Mod.query.get_or_404(mod_id)

    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje módy"}), 400

    # Kontrola kompatibility
    server_loader = get_server_loader(server)
    server_mc_version = server.build_version.mc_version if server.build_version else None
    
    if mod.loader and mod.loader != server_loader:
        return jsonify({"error": f"Mod je pro {mod.loader}, ale server je {server_loader}"}), 400
        
    if (mod.minecraft_version and server_mc_version and 
        mod.minecraft_version != server_mc_version):
        # Zkontrolujeme zda mod podporuje serverovou verzi v seznamu
        try:
            supported_versions = json.loads(mod.minecraft_versions) if mod.minecraft_versions else []
            if server_mc_version not in supported_versions:
                return jsonify({"error": f"Mod nepodporuje Minecraft {server_mc_version}"}), 400
        except json.JSONDecodeError:
            return jsonify({"error": f"Mod je pro {mod.minecraft_version}, ale server je {server_mc_version}"}), 400

    # Kontrola duplicity
    if mod in server.mods:
        return jsonify({"error": "Mod already installed"}), 400

    try:
        # Cesta k mods složce serveru
        server_mods_dir = os.path.join(BASE_SERVERS_PATH, server.name, "minecraft-server", "mods")
        os.makedirs(server_mods_dir, exist_ok=True)

        dest_path = os.path.join(server_mods_dir, os.path.basename(mod.file_path))
        shutil.copy2(mod.file_path, dest_path)

        db.session.execute(
            server_mods.insert().values(
                server_id=server.id,
                mod_id=mod.id,
                installed_at=datetime.utcnow(),
                is_active=True
            )
        )

        log_entry = ModUpdateLog(
            mod_id=mod.id,
            user_id=current_user.id,
            action="install",
            version_to=mod.version,
            notes=f"Installed to server {server.name} ({server_loader})"
        )
        db.session.add(log_entry)

        db.session.commit()
        return jsonify({"success": True, "message": "Mod installed successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@mods_api.route("/api/mods/uninstall", methods=["POST"])
@login_required
def uninstall_mod():
    server_id = request.args.get("server_id", type=int)
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    mod_id = request.json.get("mod_id")
    if not mod_id:
        return jsonify({"error": "Missing mod_id"}), 400

    server = Server.query.get_or_404(server_id)
    mod = Mod.query.get_or_404(mod_id)

    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje módy"}), 400

    if mod not in server.mods:
        return jsonify({"error": "Mod not installed"}), 400

    try:
        server_mods_dir = os.path.join(BASE_SERVERS_PATH, server.name, "minecraft-server", "mods")
        mod_path = os.path.join(server_mods_dir, os.path.basename(mod.file_path))

        if os.path.exists(mod_path):
            os.remove(mod_path)

        db.session.execute(
            server_mods.delete().where(
                (server_mods.c.server_id == server.id) &
                (server_mods.c.mod_id == mod.id)
            )
        )

        log_entry = ModUpdateLog(
            mod_id=mod.id,
            user_id=current_user.id,
            action="uninstall",
            version_from=mod.version,
            notes=f"Uninstalled from server {server.name}"
        )
        db.session.add(log_entry)

        db.session.commit()
        return jsonify({"success": True, "message": "Mod uninstalled successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@mods_api.route("/api/mods/check-updates")
@login_required
def check_mod_updates():
    server_id = request.args.get("server_id", type=int)
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    server = Server.query.get_or_404(server_id)
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje módy"}), 400

    updates = []
    for mod in server.mods:
        # TODO: implementace Modrinth API pro kontrolu aktualizací
        updates.append({
            "mod_id": mod.id,
            "name": mod.display_name or mod.name,
            "current_version": mod.version or "unknown",
            "new_version": "",
            "changelog": ""
        })

    return jsonify(updates)

@mods_api.route("/api/mods/install-from-url", methods=["POST"])
@login_required  # PŘIDAT - chybějící dekorátor
def install_mod_from_url():
    if not request.is_json:
        return jsonify({"success": False, "error": "Request must be JSON"}), 400

    data = request.get_json()
    url = data.get("url")
    download_url = data.get("download_url")
    server_id = data.get("server_id")

    if not url or not download_url or not server_id:
        return jsonify({"success": False, "error": "Chybí parametry"}), 400

    server = Server.query.get_or_404(server_id)
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    if not is_mod_server(server):
        return jsonify({"error": "Server nepodporuje módy"}), 400

    try:
        # Získání informací o projektu
        slug, project_type = extract_modrinth_slug(url)
        info = get_modrinth_info(slug)
        
        # Najdeme konkrétní verzi podle download URL
        selected_version = None
        for version in info["versions"]:
            for file in version.get("files", []):
                if file.get("url") == download_url:
                    selected_version = version
                    break
            if selected_version:
                break

        if not selected_version:
            return jsonify({"success": False, "error": "Nepodařilo se najít informace o verzi"}), 400

        # Příprava metadat PRO KONTROLU DUPLICITY
        loaders = selected_version.get("loaders", [])
        game_versions = selected_version.get("game_versions", [])
        primary_loader = loaders[0] if loaders else "unknown"
        primary_mc_version = game_versions[0] if game_versions else "unknown"
        version_number = selected_version.get("version_number", "unknown")

        # === KONTROLA DUPLICITY PŘED STAŽENÍM SOUBORU ===
        existing_mod = Mod.query.filter_by(
            name=slug,
            minecraft_version=primary_mc_version,
            loader=primary_loader
        ).first()

        # Pokud mod již existuje
        if existing_mod:
            # Kontrola, zda je již nainstalován na tomto serveru
            existing_link = db.session.execute(
                server_mods.select().where(
                    (server_mods.c.server_id == server.id) &
                    (server_mods.c.mod_id == existing_mod.id)
                )
            ).first()

            if not existing_link:
                # Přidat vztah server-mod
                db.session.execute(
                    server_mods.insert().values(
                        server_id=server.id,
                        mod_id=existing_mod.id,
                        installed_at=datetime.utcnow(),
                        is_active=True
                    )
                )
                db.session.commit()

                return jsonify({
                    "success": True,
                    "message": f"Mod {existing_mod.display_name} byl přidán na server {server.name} (již byl v systému).",
                    "mod_exists": True,
                    "mod_id": existing_mod.id
                })

            # Mod je již nainstalován na tomto serveru
            return jsonify({
                "success": False,
                "mod_exists": True,
                "mod_name": existing_mod.display_name or existing_mod.name,
                "mod_id": existing_mod.id,
                "error": f"Mod {existing_mod.display_name or slug} je již nainstalován na tomto serveru."
            }), 409

        # === STAŽENÍ SOUBORU (pouze pokud mod neexistuje) ===
        r = requests.get(download_url, timeout=15, stream=True)
        r.raise_for_status()

        filename = os.path.basename(download_url)
        
        # Uložení do centrálního úložiště
        central_path = os.path.join(BASE_MODS_PATH, "mods", "core", filename)
        os.makedirs(os.path.dirname(central_path), exist_ok=True)

        with open(central_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # === VYTVOŘENÍ NOVÉHO ZÁZNAMU MODU ===
        mod = Mod(
            name=slug,
            display_name=info["project"].get("title") or slug,
            version=version_number,
            author=", ".join([member.get("user", {}).get("username", "unknown") 
                            for member in info.get("team", [])]),
            description=info["project"].get("description", ""),
            file_path=central_path,
            download_url=download_url,
            source="modrinth",
            category=", ".join(info["project"].get("categories", [])),
            loader=primary_loader,
            minecraft_version=primary_mc_version,
            supported_loaders=json.dumps(loaders),
            minecraft_versions=json.dumps(game_versions),
            can_be_plugin=info["can_be_plugin"],
            project_type=info["project_type"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(mod)
        db.session.flush()  # Získat ID bez commit

        # === INSTALACE NA SERVER ===
        server_mods_dir = os.path.join(BASE_SERVERS_PATH, server.name, "minecraft-server", "mods")
        os.makedirs(server_mods_dir, exist_ok=True)
        dest_path = os.path.join(server_mods_dir, filename)
        shutil.copy2(central_path, dest_path)

        # Přidat vztah server-mod
        db.session.execute(
            server_mods.insert().values(
                server_id=server.id,
                mod_id=mod.id,
                installed_at=datetime.utcnow(),
                is_active=True
            )
        )

        # === LOGOVÁNÍ INSTALACE ===
        log_entry = ModUpdateLog(
            mod_id=mod.id,
            user_id=current_user.id,
            action="install",
            version_to=version_number,
            notes=f"Installed from Modrinth to server {server.name}"
        )
        db.session.add(log_entry)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{info['project_type'].title()} {mod.display_name} byl nainstalován na server {server.name}",
            "project_type": info["project_type"],
            "mod_id": mod.id
        })

    except requests.exceptions.RequestException as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Chyba při stahování souboru: {str(e)}"}), 500
    except Exception as e:
        db.session.rollback()
        # Smazat stažený soubor, pokud instalace selhala
        try:
            if 'central_path' in locals() and os.path.exists(central_path):
                os.remove(central_path)
        except:
            pass
        return jsonify({"success": False, "error": str(e)}), 500

@mods_api.route("/api/mods/get-download-info", methods=["POST"])
@login_required
def get_mod_download_info():
    data = request.get_json()
    url = data.get("url")
    server_id = data.get("server_id")

    if not url:
        return jsonify({"success": False, "error": "Chybí URL"}), 400

    try:
        # Extrahujeme slug a typ projektu
        slug, project_type = extract_modrinth_slug(url)
        info = get_modrinth_info(slug)

        # Najdeme nejlepší verzi podle serveru
        preferred_loader, preferred_version = None, None
        compatible, reason = True, ""

        if server_id:
            server = Server.query.get(server_id)
            if server and server.build_version:
                preferred_loader = get_server_loader(server)
                preferred_version = server.build_version.mc_version

        best_version = pick_best_version(info["versions"], preferred_loader, preferred_version)

        if not best_version:
            return jsonify({
                "success": False, 
                "error": f"Nenalezena kompatibilní verze pro {preferred_loader} {preferred_version}"
            }), 404

        # Najdeme primární soubor
        primary_file = None
        for file in best_version.get("files", []):
            if file.get("primary", False):
                primary_file = file
                break
        if not primary_file and best_version.get("files"):
            primary_file = best_version["files"][0]
            
        if not primary_file:
            return jsonify({"success": False, "error": "Žádný soubor k stažení"}), 404

        download_url = primary_file["url"]
        loaders = best_version.get("loaders", [])
        mc_versions = best_version.get("game_versions", [])

        # Kontrola kompatibility
        if preferred_loader and preferred_loader not in loaders:
            compatible = False
            reason = f"Mod nepodporuje loader '{preferred_loader}'. Dostupné: {', '.join(loaders)}"
        elif preferred_version and preferred_version not in mc_versions:
            compatible = False
            reason = f"Mod nepodporuje Minecraft verzi '{preferred_version}'. Dostupné: {', '.join(mc_versions)}"

        return jsonify({
            "success": True,
            "mod_name": info["project"].get("title") or info["project"].get("slug"),
            "download_url": download_url,
            "info": {
                "latest_version": {
                    "version_number": best_version.get("version_number"),
                    "changelog": best_version.get("changelog"),
                    "loaders": loaders,
                    "game_versions": mc_versions,
                    "project_type": info["project_type"]
                }
            },
            "compatible": compatible,
            "reason": reason,
            "expected_loader": preferred_loader,
            "expected_version": preferred_version,
            "project_type": info["project_type"],
            "can_be_plugin": info["can_be_plugin"]
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Neočekávaná chyba: {str(e)}"}), 500

@mods_api.route("/api/mods/client-pack/download")
@login_required
def download_client_pack():
    server_id = request.args.get("server_id", type=int)
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    server = Server.query.get_or_404(server_id)
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)

    # ZÍSKÁNÍ MODŮ - opravená verze
    client_mods = []
    used_filenames = set()  # Sledování použitých názvů souborů
    
    for mod in server.mods:
        if not hasattr(mod, 'client_side') or mod.client_side in [None, 'unknown']:
            continue
            
        if mod.client_side in ["required", "recommended"] and mod.client_side != "unsupported":
            if os.path.exists(mod.file_path):
                filename = os.path.basename(mod.file_path)
                
                # Kontrola duplicit
                if filename in used_filenames:
                    print(f"Varování: Duplicitní soubor {filename} - přeskočen")
                    continue
                    
                used_filenames.add(filename)
                client_mods.append({
                    "file_path": mod.file_path,
                    "filename": filename
                })

    if not client_mods:
        return jsonify({"error": "Žádné módy vyžadované klientem nebyly nalezeny"}), 404

    # Vytvoření ZIPu
    zip_dir = tempfile.mkdtemp()
    zip_path = os.path.join(zip_dir, f"client_modpack_{server.id}.zip")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for mod in client_mods:
                zf.write(mod["file_path"], mod["filename"])
        
        # LEPŠÍ ŘEŠENÍ PRO MAZÁNÍ - počkáme na dokončení odesílání
        @after_this_request
        def remove_file(response):
            try:
                # Počkáme chvíli, než se pokusíme smazat soubor
                import time
                time.sleep(2)  # 2 sekundy čekání
                
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                if os.path.exists(zip_dir):
                    os.rmdir(zip_dir)
            except Exception as error:
                print(f"Chyba při mazání temp souboru: {error}")
                # Není fatální - temp soubory se časem vyčistí automaticky
            return response

        return send_file(
            zip_path, 
            as_attachment=True, 
            download_name=f"{server.name}_client_mods.zip",
            # Důležité pro Windows - neukončovat spojení okamžitě
            conditional=True
        )
    
    except Exception as e:
        # Úklid při chybě
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(zip_dir):
                os.rmdir(zip_dir)
        except:
            pass
        return jsonify({"error": f"Chyba při vytváření ZIP souboru: {str(e)}"}), 500
    

#============ modpacks managment =========#
@mods_api.route('/api/modpacks/create', methods=['POST'])
@login_required
def create_modpack():
    """Vytvoří nový modpack z vybraných módů"""
    data = request.get_json()
    server_id = data.get('server_id')
    pack_name = data.get('name')
    description = data.get('description', '')
    mod_ids = data.get('mod_ids', [])
    
    if not server_id or not pack_name or not mod_ids:
        return jsonify({'success': False, 'error': 'Chybí povinné údaje'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    try:
        # Vytvoření složky pro modpacky serveru
        server_packs_dir = os.path.join(BASE_MODPACKS_PATH, str(server_id))
        os.makedirs(server_packs_dir, exist_ok=True)
        
        # Získání vybraných módů
        selected_mods = Mod.query.filter(Mod.id.in_(mod_ids)).all()
        if not selected_mods:
            return jsonify({'success': False, 'error': 'Nebyly vybrány žádné módy'}), 400
        
        # Vytvoření ZIP archivu
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = "".join(c for c in pack_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        filename = f"{safe_name}_{timestamp}.zip"
        zip_path = os.path.join(server_packs_dir, filename)
        
        total_size = 0
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for mod in selected_mods:
                if os.path.exists(mod.file_path):
                    # Použijeme originální název souboru
                    mod_filename = os.path.basename(mod.file_path)
                    zipf.write(mod.file_path, mod_filename)
                    total_size += os.path.getsize(mod.file_path)
        
        # Vytvoření záznamu v databázi
        modpack = ModPack(
            name=pack_name,
            description=description,
            server_id=server_id,
            author_id=current_user.id,
            file_path=zip_path,
            file_size=total_size,
            created_at=datetime.utcnow()
        )
        db.session.add(modpack)
        db.session.flush()  # Získat ID pro vazby
        
        # Přidání vazeb na módy
        for mod in selected_mods:
            db.session.execute(
                mod_pack_mods.insert().values(
                    mod_pack_id=modpack.id,
                    mod_id=mod.id
                )
            )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Modpack "{pack_name}" byl úspěšně vytvořen',
            'modpack_id': modpack.id,
            'file_size': total_size,
            'mod_count': len(selected_mods)
        })
        
    except Exception as e:
        db.session.rollback()
        # Smazat ZIP soubor pokud vznikla chyba
        if 'zip_path' in locals() and os.path.exists(zip_path):
            os.remove(zip_path)
        return jsonify({'success': False, 'error': f'Chyba při vytváření modpacku: {str(e)}'}), 500

@mods_api.route('/api/modpacks/list')
@login_required
def list_modpacks():
    """Vrátí seznam modpacků pro daný server"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Chybí server_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # Ověření přístupu
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
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

@mods_api.route('/api/modpacks/download/<int:pack_id>')
@login_required
def download_modpack(pack_id):
    """Stáhne modpack jako ZIP soubor"""
    modpack = ModPack.query.get_or_404(pack_id)
    
    # Ověření přístupu k serveru
    server = modpack.server
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    if not os.path.exists(modpack.file_path):
        return jsonify({'error': 'Soubor modpacku nebyl nalezen'}), 404
    
    # Inkrementovat počítadlo stažení
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

@mods_api.route('/api/modpacks/delete/<int:pack_id>', methods=['DELETE'])
@login_required
def delete_modpack(pack_id):
    """Smaže modpack"""
    modpack = ModPack.query.get_or_404(pack_id)
    
    # Ověření přístupu - pouze vlastník nebo admin serveru
    server = modpack.server
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    try:
        # Smazat soubor
        if os.path.exists(modpack.file_path):
            os.remove(modpack.file_path)
        
        # Smazat záznam z databáze
        db.session.delete(modpack)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Modpack byl smazán'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Chyba při mazání: {str(e)}'}), 500
    

@mods_api.route('/api/modpacks/update/<int:pack_id>', methods=['PUT'])
@login_required
def update_modpack(pack_id):
    """Aktualizuje existující modpack"""
    modpack = ModPack.query.get_or_404(pack_id)
    
    # Ověření přístupu
    server = modpack.server
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    mod_ids = data.get('mod_ids', [])
    
    if not name or not mod_ids:
        return jsonify({'success': False, 'error': 'Chybí povinné údaje'}), 400
    
    try:
        # Získání vybraných módů
        selected_mods = Mod.query.filter(Mod.id.in_(mod_ids)).all()
        if not selected_mods:
            return jsonify({'success': False, 'error': 'Nebyly vybrány žádné módy'}), 400
        
        # Aktualizace metadat
        modpack.name = name
        modpack.description = description
        modpack.updated_at = datetime.utcnow()
        
        # Aktualizace vazeb na módy
        db.session.execute(
            mod_pack_mods.delete().where(mod_pack_mods.c.mod_pack_id == modpack.id)
        )
        
        for mod in selected_mods:
            db.session.execute(
                mod_pack_mods.insert().values(
                    mod_pack_id=modpack.id,
                    mod_id=mod.id
                )
            )
        
        # Vytvoření nového ZIP archivu
        server_packs_dir = os.path.join(BASE_MODPACKS_PATH, str(server.id))
        old_zip_path = modpack.file_path
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        filename = f"{safe_name}_{timestamp}.zip"
        new_zip_path = os.path.join(server_packs_dir, filename)
        
        total_size = 0
        with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for mod in selected_mods:
                if os.path.exists(mod.file_path):
                    mod_filename = os.path.basename(mod.file_path)
                    zipf.write(mod.file_path, mod_filename)
                    total_size += os.path.getsize(mod.file_path)
        
        # Aktualizace cesty a velikosti souboru
        modpack.file_path = new_zip_path
        modpack.file_size = total_size
        
        # Smazat starý ZIP soubor
        if os.path.exists(old_zip_path) and old_zip_path != new_zip_path:
            os.remove(old_zip_path)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Modpack "{name}" byl úspěšně aktualizován',
            'file_size': total_size,
            'mod_count': len(selected_mods)
        })
        
    except Exception as e:
        db.session.rollback()
        # Smazat nový ZIP soubor pokud vznikla chyba
        if 'new_zip_path' in locals() and os.path.exists(new_zip_path):
            os.remove(new_zip_path)
        return jsonify({'success': False, 'error': f'Chyba při aktualizaci modpacku: {str(e)}'}), 500