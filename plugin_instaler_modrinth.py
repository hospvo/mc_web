import requests
from urllib.parse import urlparse


def extract_slug_from_url(url):
    """Extract the project slug from a Modrinth URL."""
    parsed = urlparse(url)
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


def get_download_url(url):
    """Get the download URL for a Modrinth plugin version."""
    try:
        slug = extract_slug_from_url(url)
        
        response = requests.get(f"https://api.modrinth.com/v2/project/{slug}/version")
        response.raise_for_status()
        versions = response.json()
        
        if not versions:
            raise ValueError("No versions found for this plugin")
        
        # Find compatible version (prefer Paper, Purpur, then Spigot)
        compatible_version = versions[0]  # default to first version
        
        for version in versions:
            if "paper" in version.get("loaders", []):
                compatible_version = version
                break
            elif "purpur" in version.get("loaders", []):
                compatible_version = version
                break
            elif "spigot" in version.get("loaders", []):
                compatible_version = version
                break
        
        if not compatible_version.get("files") or not compatible_version["files"][0].get("url"):
            raise ValueError("Could not find download URL for this plugin version")
        
        return compatible_version["files"][0]["url"]
        
    except Exception as e:
        print(f"[ERROR] Failed to get download URL: {str(e)}")
        raise ValueError(f"Failed to get download URL: {str(e)}")


def handle_web_request(url):
    """Handle the request from the web interface to get download URL."""
    try:
        if not url:
            return {"success": False, "error": "Please enter a valid Modrinth plugin URL."}
        
        # Validate it's a Modrinth URL
        parsed = urlparse(url)
        if parsed.netloc != "modrinth.com" or not parsed.path.startswith("/plugin/"):
            return {
                "success": False, 
                "error": "Only Modrinth plugin URLs are supported (format: https://modrinth.com/plugin/plugin-name)"
            }
        
        download_url = get_download_url(url)
        plugin_info = get_modrinth_plugin_info(extract_slug_from_url(url))
        
        return {
            "success": True,
            "download_url": download_url,
            "plugin_name": plugin_info["basic_info"]["title"],
            "plugin_version": plugin_info["latest_version"]["version_number"]
        }
        
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Failed to process plugin: {str(e)}"}