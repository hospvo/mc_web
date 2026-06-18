import os
import re
import shutil
import time

from app_config import BASE_BUILD_PATH, BASE_SERVERS_PATH, PORT_RANGE_END, PORT_RANGE_START
from models import BuildVersion, Server, User, db


SERVICE_LEVELS = {
    1: {"label": "Basic", "cores": 2, "ram": "4 GB RAM"},
    2: {"label": "Advanced", "cores": 4, "ram": "6 GB RAM"},
    3: {"label": "Premium", "cores": 6, "ram": "8 GB RAM"},
}

ALLOWED_GAMEMODES = {"survival", "creative", "adventure", "spectator"}
ALLOWED_DIFFICULTIES = {"peaceful", "easy", "normal", "hard"}


def create_server_from_payload(data):
    server_name = (data.get("name") or "").strip()
    owner_id = _to_int(data.get("owner_id"))
    service_level = _to_int(data.get("service_level"))
    build_version_id = _to_int(data.get("build_version_id"))

    if not server_name or not owner_id or not service_level or not build_version_id:
        return False, "Vyplňte název, vlastníka, úroveň a build verzi.", None

    if not re.match(r"^[A-Za-z0-9_-]{3,32}$", server_name):
        return False, "Název serveru může mít 3-32 znaků a obsahovat jen písmena, čísla, pomlčku a podtržítko.", None

    if service_level not in SERVICE_LEVELS:
        return False, "Neplatná úroveň serveru.", None

    if Server.query.filter_by(name=server_name).first():
        return False, "Server s tímto názvem už existuje.", None

    owner = User.query.get(owner_id)
    build_version = BuildVersion.query.get(build_version_id)
    if not owner or not build_version:
        return False, "Vybraný uživatel nebo build verze nebyla nalezena.", None

    paths = _server_paths_for_name(server_name)
    if os.path.exists(paths["server_dir"]):
        return False, "Složka pro tento server už na disku existuje. Zvolte jiný název nebo ji nejdřív zkontrolujte ručně.", None

    server = Server(
        name=server_name,
        owner_id=owner.id,
        service_level=service_level,
        server_port=25565,
        query_port=25565,
        diagnostic_server_port=None,
        build_version_id=build_version.id,
    )

    try:
        db.session.add(server)
        db.session.flush()

        minecraft_port, query_port = _find_available_port_pair(server.id)
        server.server_port = minecraft_port
        server.query_port = query_port

        os.makedirs(paths["backup_path"], exist_ok=True)
        os.makedirs(paths["server_path"], exist_ok=True)

        _copy_build_files(build_version, paths["server_path"], server.id)
        _create_start_bat(paths["server_path"], server.id, build_version.build_type.name, service_level)
        _write_server_properties(
            paths["server_path"],
            minecraft_port,
            query_port,
            _build_server_properties(data),
        )
        _accept_eula(paths["server_path"])

        db.session.commit()
        return True, f"Server '{server.name}' byl vytvořen.", server
    except Exception:
        db.session.rollback()
        if os.path.exists(paths["server_dir"]):
            shutil.rmtree(paths["server_dir"], ignore_errors=True)
        raise


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _server_folder_name(server_name):
    return server_name.replace(" ", "_").lower()


def _server_paths_for_name(server_name):
    server_dir = os.path.join(BASE_SERVERS_PATH, _server_folder_name(server_name))
    return {
        "server_dir": server_dir,
        "server_path": os.path.join(server_dir, "minecraft-server"),
        "backup_path": os.path.join(server_dir, "mcbackups"),
    }


def _version_folder_name(build_version):
    if build_version.build_number:
        return f"{build_version.mc_version}-{build_version.build_number}"
    return build_version.mc_version


def _build_source_path(build_version):
    if build_version.file_path and os.path.exists(build_version.file_path):
        return build_version.file_path

    version_path = os.path.join(
        BASE_BUILD_PATH,
        build_version.build_type.name.upper(),
        "versions",
        _version_folder_name(build_version),
    )
    if not os.path.isdir(version_path):
        return None

    preferred = os.path.join(version_path, "server.jar")
    if os.path.exists(preferred):
        return preferred

    jar_files = [
        os.path.join(version_path, file_name)
        for file_name in os.listdir(version_path)
        if file_name.endswith(".jar") and file_name != "installer.jar"
    ]
    return jar_files[0] if jar_files else None


def _copy_build_files(build_version, target_server_path, server_id):
    source_path = _build_source_path(build_version)
    if not source_path:
        raise FileNotFoundError("Soubor buildu nebyl nalezen. Nejdřív proveď synchronizaci buildů.")

    target_jar = os.path.join(target_server_path, f"server_{server_id}.jar")
    build_name = build_version.build_type.name.upper()

    if build_name == "FORGE":
        source_dir = os.path.dirname(source_path)
        for item in os.listdir(source_dir):
            if item == "installer.jar":
                continue
            src = os.path.join(source_dir, item)
            dst = os.path.join(target_server_path, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif os.path.isfile(src):
                shutil.copy2(src, dst)

        copied_jar = os.path.join(target_server_path, os.path.basename(source_path))
        if os.path.exists(copied_jar) and copied_jar != target_jar:
            if os.path.exists(target_jar):
                os.remove(target_jar)
            shutil.move(copied_jar, target_jar)
    else:
        shutil.copy2(source_path, target_jar)

    if not os.path.exists(target_jar):
        raise FileNotFoundError("Nepodařilo se připravit server jar.")


def _create_start_bat(server_path, server_id, build_type_name, service_level):
    jar_filename = f"server_{server_id}.jar"
    max_ram = {1: "4G", 2: "6G", 3: "8G"}.get(service_level, "4G")
    min_ram = {1: "2G", 2: "3G", 3: "4G"}.get(service_level, "2G")
    title = f"Minecraft {build_type_name} Server {server_id}"
    bat_content = f"""@echo off
title {title}
echo Starting {title}...

if defined MINECRAFT_JAVA_PATH (
    "%MINECRAFT_JAVA_PATH%" -Xmx{max_ram} -Xms{min_ram} -jar "{jar_filename}" nogui
) else (
    java -Xmx{max_ram} -Xms{min_ram} -jar "{jar_filename}" nogui
)

pause
"""
    with open(os.path.join(server_path, "start.bat"), "w", encoding="utf-8") as bat_file:
        bat_file.write(bat_content)


def _build_server_properties(data):
    gamemode = (data.get("gamemode") or "survival").strip().lower()
    difficulty = (data.get("difficulty") or "normal").strip().lower()
    if gamemode not in ALLOWED_GAMEMODES:
        gamemode = "survival"
    if difficulty not in ALLOWED_DIFFICULTIES:
        difficulty = "normal"

    max_players = _to_int(data.get("max_players")) or 20
    max_players = min(max(max_players, 1), 200)

    seed = (data.get("seed") or "").strip()
    motd = (data.get("motd") or "Minecraft Server Manager").strip()[:120]

    return {
        "motd": motd,
        "max-players": str(max_players),
        "gamemode": gamemode,
        "difficulty": difficulty,
        "pvp": _bool_property(data.get("pvp"), True),
        "online-mode": _bool_property(data.get("online_mode"), False),
        "enable-command-block": _bool_property(data.get("enable_command_block"), False),
        "spawn-protection": str(min(max(_to_int(data.get("spawn_protection")) or 0, 0), 32)),
        "level-seed": seed,
    }


def _bool_property(value, default):
    if value is None or value == "":
        return "true" if default else "false"
    return "true" if str(value).lower() in {"1", "true", "yes", "on"} else "false"


def _write_server_properties(server_path, server_port, query_port, extra_properties):
    properties = {
        "server-port": str(server_port),
        "query.port": str(query_port),
        "enable-query": "true",
        **extra_properties,
    }

    content = [
        "# Minecraft server properties",
        "# Generated by Minecraft Hosting admin",
    ]
    content.extend(f"{key}={value}" for key, value in properties.items() if value != "")

    with open(os.path.join(server_path, "server.properties"), "w", encoding="utf-8") as prop_file:
        prop_file.write("\n".join(content) + "\n")


def _accept_eula(server_path):
    with open(os.path.join(server_path, "eula.txt"), "w", encoding="utf-8") as eula_file:
        eula_file.write("# By changing the setting below to TRUE you agree to the Minecraft EULA.\n")
        eula_file.write(f"#{time.strftime('%a %b %d %H:%M:%S %Z %Y')}\n")
        eula_file.write("eula=true\n")


def _find_available_port_pair(server_id):
    used_ports = set()
    for server in Server.query.all():
        if server.id == server_id:
            continue
        used_ports.add(server.server_port)
        if server.query_port:
            used_ports.add(server.query_port)

    port = PORT_RANGE_START
    while port <= PORT_RANGE_END:
        if port % 2 == 0 and port not in used_ports and (port + 1) not in used_ports:
            return port, port + 1
        port += 1
    raise ValueError("Nebyl nalezen žádný volný port.")
