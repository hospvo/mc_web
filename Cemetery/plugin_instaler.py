import requests
from urllib.parse import urlparse


def extract_slug_from_url(url, source):
    """Extract the project slug from a Modrinth or Hangar URL."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    
    if source == "modrinth":
        if len(path_parts) < 2 or path_parts[0] != "plugin":
            raise ValueError("Invalid Modrinth plugin URL")
        return path_parts[1]
    elif source == "hangar":
        if not path_parts:
            raise ValueError("Invalid Hangar plugin URL")
        return path_parts[-1]  # vždy vezme poslední část cesty jako slug
    else:
        raise ValueError("Unknown source platform")


def get_plugin_info(url, source="modrinth"):
    """Get comprehensive information about a plugin from Modrinth or Hangar."""
    slug = extract_slug_from_url(url, source)
    
    if source == "modrinth":
        return get_modrinth_plugin_info(slug)
    elif source == "hangar":
        return get_hangar_plugin_info(slug)
    else:
        raise ValueError("Unsupported platform")


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


def get_hangar_plugin_info(slug):
    """Get plugin info from Hangar API."""
    # Get project info
    project_url = f"https://hangar.papermc.io/api/v1/projects/{slug}"
    response = requests.get(project_url)
    response.raise_for_status()
    project_info = response.json()
    
    # Get versions info
    versions_url = f"https://hangar.papermc.io/api/v1/projects/{slug}/versions"
    response = requests.get(versions_url)
    versions_info = response.json() if response.status_code == 200 else {}
    
    # Get latest version details
    latest_version = None
    if versions_info and isinstance(versions_info, dict):
        versions_list = versions_info.get("result", [])
        if versions_list:
            latest_version = versions_list[0]
    
    # Extract source URL from links
    source_url = None
    for link_group in project_info.get("settings", {}).get("links", []):
        for link in link_group.get("links", []):
            if link.get("name") == "Source":
                source_url = link.get("url")
                break
    
    # Structure the information
    result = {
        "source": "hangar",
        "basic_info": {
            "title": project_info.get("name"),
            "slug": project_info.get("namespace", {}).get("slug"),
            "description": project_info.get("description"),
            "categories": [project_info.get("category")] if project_info.get("category") else [],
            "project_type": "plugin",
            "downloads": project_info.get("stats", {}).get("downloads"),
            "followers": project_info.get("stats", {}).get("watchers"),
            "source_url": source_url,
            "date_created": project_info.get("createdAt"),
            "date_updated": project_info.get("lastUpdated"),
            "status": "approved" if project_info.get("visibility") == "public" else project_info.get("visibility"),
        },
        "team": [
            {
                "username": project_info.get("namespace", {}).get("owner"),
                "role": "owner",
            }
        ],
        "latest_version": None,
        "dependencies": {
            "projects": [],
            "versions": [],
        },
    }
    
    if latest_version:
        result["latest_version"] = {
            "version_number": latest_version.get("name"),
            "changelog": latest_version.get("description"),
            "date_published": latest_version.get("createdAt"),
            "downloads": latest_version.get("stats", {}).get("downloads"),
            "loaders": ["PAPER"],
            "game_versions": project_info.get("supportedPlatforms", {}).get("PAPER", []),
            "download_url": f"https://hangar.papermc.io/api/v1/projects/{slug}/versions/{latest_version.get('name')}/download",
        }
    
    return result


def get_download_url(url, source="modrinth"):
    """Get the download URL for a plugin version - modified to use Hangar CDN like the second script"""
    try:
        if source == "modrinth":
            slug_match = url_match_modrinth(url)
            if not slug_match:
                raise ValueError("Invalid Modrinth URL")
            
            slug = slug_match
            response = requests.get(f"https://api.modrinth.com/v2/project/{slug}/version")
            response.raise_for_status()
            versions = response.json()
            if not versions:
                raise ValueError("No versions found")
            
            return versions[0]["files"][0]["url"]
            
        elif source == "hangar":
            print(f"[DEBUG] {source}")
            parts = url_match_hangar(url)
            if not parts:
                raise ValueError("Invalid Hangar URL")
            
            author, name = parts
            
            # Print debug info about the parsed URL
            print(f"[DEBUG] Hangar URL parsed - Author: {author}, Project: {name}")
            
            # Získání informací o projektu
            project_url = f"https://hangar.papermc.io/api/v1/projects/{author}/{name}"
            print(f"[DEBUG] Fetching project info from: {project_url}")
            
            project_res = requests.get(project_url)
            project_res.raise_for_status()
            project_data = project_res.json()
            print(f"[DEBUG] Project data received: {project_data}")
            
            # Získání nejnovější verze
            versions_url = f"https://hangar.papermc.io/api/v1/projects/{author}/{name}/versions"
            print(f"[DEBUG] Fetching versions from: {versions_url}")
            
            versions_res = requests.get(versions_url)
            versions_res.raise_for_status()
            versions_data = versions_res.json()
            print(f"[DEBUG] Versions data received: {versions_data}")
            
            if not versions_data.get("result"):
                raise ValueError("No versions found")
            
            latest_version = versions_data["result"][0]["name"]
            print(f"[DEBUG] Latest version found: {latest_version}")
            
            # Generování CDN URL podle druhého skriptu
            download_url = f"https://hangarcdn.papermc.io/plugins/{author}/{name}/versions/{latest_version}/PAPER/{name}-Bukkit-{latest_version}.jar"
            print(f"[DEBUG] Generated download URL: {download_url}")
            
            return download_url
            
        else:
            raise ValueError("Unknown platform")
            
    except Exception as e:
        print(f"[ERROR] Failed to get download URL: {str(e)}")
        raise ValueError(f"Failed to get download URL: {str(e)}")


def url_match_modrinth(url):
    """Helper function to match Modrinth URLs."""
    parsed = urlparse(url)
    if parsed.netloc != "modrinth.com":
        return None
    
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2 and path_parts[0] == "plugin":
        return path_parts[1]
    return None


def url_match_hangar(url):
    """Helper function to match Hangar URLs."""
    parsed = urlparse(url)
    print(f"nalazená url je {parsed}")
    if parsed.netloc not in ["hangar.papermc.io", "hangar.p.apolloproject.dev"]:
        return None
    
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2:
        return (path_parts[0], path_parts[1])
    return None


# Web interface compatible function
def handle_web_request(platform, url):
    """Handle the request from the web interface to get download URL."""
    try:
        if not url:
            return {"success": False, "error": "Please enter a valid plugin URL."}
        
        download_url = get_download_url(url, platform.lower())
        return {"success": True, "download_url": download_url}
        
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Failed to get link: {str(e)}"}