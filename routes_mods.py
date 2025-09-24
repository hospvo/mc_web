import os
import shutil
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from urllib.parse import urlparse


#from app import app
from models import db, Server, Mod, ModConfig, ModUpdateLog, BuildType, BuildVersion, server_mods
from mc_server import BASE_FORGE_MODS_PATH,  BASE_SERVERS_PATH

# Blueprint
mods_api = Blueprint("mods_api", __name__)


def is_forge_server(server: Server) -> bool:
    """Ověří, že server má Forge build"""
    return server.build_version and server.build_version.build_type.name.upper() == "FORGE"


# ---- Pomocné funkce pro Modrinth ----

def extract_modrinth_slug(url):
    """Vrátí slug z URL typu https://modrinth.com/mod/<slug>"""
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "mod":
        raise ValueError("Neplatná Modrinth URL (očekáváno https://modrinth.com/mod/<nazev>)")
    return parts[1]


def get_modrinth_info(slug):
    """Vrátí detailní info o projektu z Modrinthu."""
    project = requests.get(f"https://api.modrinth.com/v2/project/{slug}").json()
    versions = requests.get(f"https://api.modrinth.com/v2/project/{slug}/version").json()
    team = requests.get(f"https://api.modrinth.com/v2/project/{slug}/members").json()

    return {
        "project": project,
        "versions": versions,
        "team": team,
    }


def pick_best_version(versions, preferred_loader=None, preferred_mc_version=None):
    """Vybere nejlepší verzi modu podle loaderu a MC verze."""
    for v in versions:
        loaders = v.get("loaders", [])
        mc_versions = v.get("game_versions", [])
        if ((not preferred_loader or preferred_loader in loaders) and
            (not preferred_mc_version or preferred_mc_version in mc_versions)):
            return v
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

    if not is_forge_server(server):
        return jsonify({"error": "Server není Forge build"}), 400

    mods = []
    for mod in server.mods:
        mods.append({
            "id": mod.id,
            "name": mod.name,
            "display_name": mod.display_name or mod.name,
            "version": mod.version,
            "author": mod.author,
            "is_active": True,
            "installed_at": None,  # můžeš doplnit ze server_mods
            "description": mod.description
        })

    return jsonify(mods)


@mods_api.route("/api/mods/available")
@login_required
def get_available_mods():
    search = request.args.get("search", "").lower()
    category = request.args.get("category", "all")
    server_id = request.args.get("server_id", type=int)

    query = Mod.query

    if search:
        query = query.filter(db.or_(
            Mod.name.ilike(f"%{search}%"),
            Mod.display_name.ilike(f"%{search}%"),
            Mod.description.ilike(f"%{search}%")
        ))

    if category != "all":
        query = query.filter_by(category=category)

    mods = query.all()

    # pokud je zadaný server_id, filtruj podle Forge verze serveru
    if server_id:
        server = Server.query.get(server_id)
        if server and is_forge_server(server):
            mc_version = server.build_version.mc_version
            mods = [m for m in mods if not m.compatible_with or mc_version in m.compatible_with]

    return jsonify([{
        "id": m.id,
        "name": m.name,
        "display_name": m.display_name or m.name,
        "version": m.version,
        "author": m.author,
        "description": m.description,
        "category": m.category,
        "compatible_with": m.compatible_with
    } for m in mods])


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

    if not is_forge_server(server):
        return jsonify({"error": "Server není Forge build"}), 400

    # Kontrola duplicity
    if mod in server.mods:
        return jsonify({"error": "Mod already installed"}), 400

    try:
        server_mods_dir = os.path.join(BASE_FORGE_MODS_PATH, server.name, "mods")
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
            notes=f"Installed to server {server.name}"
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

    if not is_forge_server(server):
        return jsonify({"error": "Server není Forge build"}), 400

    if mod not in server.mods:
        return jsonify({"error": "Mod not installed"}), 400

    try:
        server_mods_dir = os.path.join(BASE_FORGE_MODS_PATH, server.name, "mods")
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

    if not is_forge_server(server):
        return jsonify({"error": "Server není Forge build"}), 400

    updates = []
    for mod in server.mods:
        # TODO: implementace Modrinth API – podobně jako u pluginů
        # Zatím vracíme prázdné
        updates.append({
            "mod_id": mod.id,
            "name": mod.display_name or mod.name,
            "current_version": mod.version or "unknown",
            "new_version": "",  # ← místo None dát prázdný string
            "changelog": ""
        })

    return jsonify(updates)

@mods_api.route("/api/mods/install-from-url", methods=["POST"])
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

    if not is_forge_server(server):
        return jsonify({"error": "Server není Forge build"}), 400

    try:
        r = requests.get(download_url, timeout=15, stream=True)
        r.raise_for_status()

        filename = os.path.basename(download_url)

        # centrální archiv všech modů
        central_path = os.path.join(BASE_FORGE_MODS_PATH, "mods", "core", filename)
        os.makedirs(os.path.dirname(central_path), exist_ok=True)

        with open(central_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # ⚡️ skutečná složka daného serveru
        server_mods_dir = os.path.join(BASE_SERVERS_PATH, server.name, "minecraft-server", "mods")
        os.makedirs(server_mods_dir, exist_ok=True)
        dest_path = os.path.join(server_mods_dir, filename)
        shutil.copy2(central_path, dest_path)

        # zápis do DB
        mod = Mod(
            name=os.path.splitext(filename)[0],
            display_name=os.path.splitext(filename)[0],
            version="unknown",
            author="unknown",
            description="",
            file_path=central_path,  # originální uložená cesta
            download_url=download_url,
            source="modrinth",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(mod)
        db.session.flush()

        db.session.execute(
            server_mods.insert().values(
                server_id=server.id,
                mod_id=mod.id,
                installed_at=datetime.utcnow(),
                is_active=True
            )
        )

        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Mod {filename} byl nainstalován na server {server.name}"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



@mods_api.route("/api/mods/get-download-info", methods=["POST"])
@login_required
def get_mod_download_info():
    data = request.get_json()
    url = data.get("url")
    server_id = data.get("server_id")

    if not url:
        return jsonify({"success": False, "error": "Chybí URL"}), 400

    try:
        slug = extract_modrinth_slug(url)
        info = get_modrinth_info(slug)

        # Najdeme nejlepší verzi podle serveru
        preferred_loader, preferred_version = None, None
        compatible, reason = True, ""

        if server_id:
            server = Server.query.get(server_id)
            if server and server.build_version:
                preferred_loader = server.build_version.build_type.name.lower()
                preferred_version = server.build_version.mc_version

        best_version = pick_best_version(info["versions"], preferred_loader, preferred_version)

        if best_version:
            download_url = best_version["files"][0]["url"]

            # zkontrolujeme client/server side na úrovni projektu
            client_side = info["project"].get("client_side", "unknown")
            server_side = info["project"].get("server_side", "unknown")

            warning = ""
            if server_side == "unsupported":
                warning = "⚠️ Tento mod je pouze client-side a na serveru nebude fungovat!"

            loaders = best_version.get("loaders", [])
            mc_versions = best_version.get("game_versions", [])

            if preferred_loader and preferred_loader not in loaders:
                compatible = False
                reason = f"Mod nepodporuje loader '{preferred_loader}'"
            elif preferred_version and preferred_version not in mc_versions:
                compatible = False
                reason = f"Mod nepodporuje Minecraft verzi '{preferred_version}'"
        else:
            return jsonify({"success": False, "error": "Žádné verze nenačteny"}), 404

        return jsonify({
            "success": True,
            "mod_name": info["project"].get("title") or info["project"].get("slug"),
            "download_url": download_url,
            "info": {
                "latest_version": {
                    "version_number": best_version.get("version_number"),
                    "changelog": best_version.get("changelog"),
                    "loaders": best_version.get("loaders", []),
                    "game_versions": best_version.get("game_versions", []),
                    "client_side": client_side,
                    "server_side": server_side,
                }
            },
            "compatible": compatible,
            "reason": reason,
            "warning": warning,   # 👈 nové pole pro varování
            "expected_loader": preferred_loader,
            "expected_version": preferred_version,
})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
