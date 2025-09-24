import requests
from urllib.parse import urlparse
from models import db, Server, BuildVersion


def get_server_loader_and_version(server_id):
    """Vrátí loader (typ buildu) a MC verzi pro daný server_id."""
    server = Server.query.get(server_id)
    if not server or not server.build_version:
        raise ValueError("Nelze načíst build informace pro server.")

    build = server.build_version
    loader = build.build_type.name.lower()  # např. "paper", "purpur", "folia"
    version = build.mc_version              # např. "1.21.1"

    return loader, version

def extract_slug_from_url(url):
    """Extract the project slug from a Modrinth URL."""
    parsed = urlparse(url)
    print(f"[DEBUG] URL path: {parsed.path}")
    path_parts = parsed.path.strip("/").split("/")
    
    if len(path_parts) < 2 or path_parts[0] != "plugin":
        raise ValueError("Invalid Modrinth plugin URL. Expected format: https://modrinth.com/plugin/plugin-name")
    
    return path_parts[1]


def get_plugin_info(url):
    """Get comprehensive information about a plugin from Modrinth."""
    slug = extract_slug_from_url(url)
    return get_modrinth_plugin_info(slug)


def get_modrinth_plugin_info(slug):
    """Get plugin info from Modrinth API."""
    # Get project info
    project_url = f"https://api.modrinth.com/v2/project/{slug}"
    response = requests.get(project_url)
    response.raise_for_status()
    project_info = response.json()
    
    # Get team members (authors)
    team_url = f"https://api.modrinth.com/v2/project/{slug}/members"
    response = requests.get(team_url)
    team_info = response.json() if response.status_code == 200 else []
    
    # Get latest version info
    versions_url = f"https://api.modrinth.com/v2/project/{slug}/version"
    response = requests.get(versions_url)
    versions_info = response.json() if response.status_code == 200 else []
    
    # Get dependencies
    dependencies_url = f"https://api.modrinth.com/v2/project/{slug}/dependencies"
    response = requests.get(dependencies_url)
    dependencies_info = response.json() if response.status_code == 200 else {}

    # Structure the information
    return {
        "source": "modrinth",
        "basic_info": {
            "title": project_info.get("title"),
            "slug": project_info.get("slug"),
            "description": project_info.get("description"),
            "categories": project_info.get("categories", []),
            "client_side": project_info.get("client_side"),
            "server_side": project_info.get("server_side"),
            "project_type": project_info.get("project_type"),
            "downloads": project_info.get("downloads"),
            "followers": project_info.get("followers"),
            "license": project_info.get("license"),
            "source_url": project_info.get("source_url"),
            "wiki_url": project_info.get("wiki_url"),
            "discord_url": project_info.get("discord_url"),
            "donation_urls": project_info.get("donation_urls", []),
            "date_created": project_info.get("published"),
            "date_updated": project_info.get("updated"),
            "status": project_info.get("status"),
        },
        "team": [
            {
                "username": member.get("user", {}).get("username"),
                "role": member.get("role"),
            }
            for member in team_info
        ],
        "latest_version": {
            "version_number": versions_info[0].get("version_number") if versions_info else None,
            "changelog": versions_info[0].get("changelog") if versions_info else None,
            "date_published": versions_info[0].get("date_published") if versions_info else None,
            "downloads": versions_info[0].get("downloads") if versions_info else None,
            "loaders": versions_info[0].get("loaders", []) if versions_info else [],
            "game_versions": versions_info[0].get("game_versions", []) if versions_info else [],
        } if versions_info else None,
        "dependencies": {
            "projects": [dep.get("project_id") for dep in dependencies_info.get("projects", [])],
            "versions": [dep.get("version_id") for dep in dependencies_info.get("versions", [])],
        },
    }


def get_download_url(url, server_id=None):
    try:
        slug = extract_slug_from_url(url)
        response = requests.get(f"https://api.modrinth.com/v2/project/{slug}/version")
        response.raise_for_status()
        versions = response.json()

        if not versions:
            raise ValueError("No versions found for this plugin")

        preferred_loader, preferred_mc_version = None, None
        if server_id:
            preferred_loader, preferred_mc_version = get_server_loader_and_version(server_id)

        # 1) přesná shoda (loader + MC verze)
        for version in versions:
            if preferred_loader in version.get("loaders", []) and preferred_mc_version in version.get("game_versions", []):
                return pick_file(version, preferred_loader), version, "exact"

        # 2) fallback – loader sedí, MC verze ne
        for version in versions:
            if preferred_loader in version.get("loaders", []):
                return pick_file(version, preferred_loader), version, "fallback"

        # 3) nic nenalezeno
        raise ValueError(f"Nenalezena žádná verze pro loader '{preferred_loader}' (server má MC {preferred_mc_version})")

    except Exception as e:
        raise ValueError(f"Failed to get download URL: {str(e)}")


def pick_file(version, loader):
    """Vybere správný soubor pro loader z files[]"""
    files = version.get("files", [])
    if not files:
        return None
    # 1) loader v názvu
    for f in files:
        fname = f.get("filename", "").lower()
        if loader and loader in fname:
            return f["url"]
    # 2) primary soubor
    for f in files:
        if f.get("primary"):
            return f["url"]
    # 3) fallback
    return files[0]["url"]



def handle_web_request(url, server_id=None):
    try:
        if not url:
            return {"success": False, "error": "Please enter a valid Modrinth plugin URL."}

        parsed = urlparse(url)
        if parsed.netloc != "modrinth.com" or not parsed.path.startswith("/plugin/"):
            return {
                "success": False,
                "error": "Only Modrinth plugin URLs are supported (format: https://modrinth.com/plugin/plugin-name)"
            }

        slug = extract_slug_from_url(url)
        plugin_info = get_modrinth_plugin_info(slug)
        plugin_name = plugin_info["basic_info"]["title"] or plugin_info["basic_info"]["slug"]

        preferred_loader, preferred_version = None, None
        if server_id:
            try:
                preferred_loader, preferred_version = get_server_loader_and_version(server_id)
            except Exception as e:
                print("[WARN] Nelze zjistit loader a verzi:", e)

        # Získání URL + režimu (exact/fallback)
        download_url, matched_version, mode = get_download_url(url, server_id=server_id)

        # Nastavení kompatibility
        compatible = True
        reason = ""
        if mode == "fallback":
            compatible = False
            reason = (
                f"Pro loader '{preferred_loader}' a Minecraft verzi '{preferred_version}' "
                f"nebyl nalezen plugin. "
                f"Používá se fallback pro verze {', '.join(matched_version.get('game_versions', []))}."
            )

        return {
            "success": True,
            "download_url": download_url,
            "plugin_name": plugin_name,
            "info": plugin_info,
            "compatible": compatible,
            "reason": reason,
            "expected_loader": preferred_loader,
            "expected_version": preferred_version,
            "mode": mode
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



