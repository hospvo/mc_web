import os
import requests
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from models import db, Plugin
from app import app

# Konfigurace
BASE_PATH = r"C:\Users\hospv\Documents\minecraft_plugins"
PLUGINS_DIR = os.path.join(BASE_PATH, "plugins/core")
TEMP_DIR = os.path.join(BASE_PATH, "temp")
LOG_FILE = os.path.join(BASE_PATH, "plugin_import_log.txt")
# Seznam pluginů ke stažení (slugy z Modrinth)
MODRINTH_PLUGINS = [
    "xss83sOY",  # AdvancedServerList
    "HFTnFHKn",  # AntiPopup
    "3IEZ9vol",  # AuthMe
    "EeyAn23L",  # FancyNpcs
    "fALzjamp",  # Chunky
    "luckperms", # LuckPerms
]

# Manuální URL pro pluginy, které nejsou na Modrinth
MANUAL_PLUGIN_URLS = [
    "https://www.spigotmc.org/resources/betterboard.96393/download?version=577015",
    "https://github.com/BetterGUI-MC/BetterGUI/releases/download/10.2/bettergui-10.2-shaded.jar",
    "https://github.com/BlueMap-Minecraft/BlueMap/releases/download/v5.7/bluemap-5.7-paper.jar",
    "https://github.com/DiscordSRV/DiscordSRV/releases/download/v1.29.0/DiscordSRV-Build-1.29.0.jar",
    "https://github.com/FancyMcPlugins/FancyHolograms/releases/download/v2.4.2/FancyHolograms-2.4.2.jar",
    "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot",
    "https://github.com/SkinsRestorer/SkinsRestorer/releases/download/15.6.3/SkinsRestorer.jar",
]

def download_file(url, destination):
    """Stáhne soubor z URL do cílového umístění"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        log_error(f"Failed to download {url}: {str(e)}")
        return False

def log_message(message):
    """Zaznamená zprávu do logu"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now(timezone.utc)}] {message}\n")

def log_error(message):
    """Zaznamená chybu do logu"""
    log_message(f"ERROR: {message}")

def get_plugin_name_from_url(url):
    """Získání názvu pluginů z URL"""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    return os.path.splitext(filename)[0]

def extract_version_from_filename(filename):
    """Pokusí se extrahovat verzi z názvu souboru"""
    # Odstraníme příponu .jar
    name = filename.replace('.jar', '')
    
    # Hledáme číslo verze (např. -1.2.3 nebo v2.0)
    parts = name.split('-')
    for part in reversed(parts):
        if part.startswith('v') and part[1:].replace('.', '').isdigit():
            return part[1:]
        if part.replace('.', '').isdigit():
            return part
    
    # Pokud nenajdeme verzi, vrátíme "1.0.0"
    return "1.0.0"

def get_plugin_display_name(plugin_name):
    """Vytvoří hezčí zobrazovaný název z názvu souboru"""
    # Odstraníme verzi a příponu
    base_name = plugin_name.split('-')[0]
    # Nahradíme speciální znaky
    return base_name.replace('_', ' ').title()

def get_plugin_category(plugin_name):
    """Určí kategorii pluginu podle názvu"""
    plugin_name = plugin_name.lower()
    protection_plugins = ['worldguard', 'authme', 'advancedban']
    admin_plugins = ['discordsrv', 'betterboard', 'essentials']
    optimization_plugins = ['chunky', 'spark', 'clearlagg']
    
    if any(p in plugin_name for p in protection_plugins):
        return 'protection'
    elif any(p in plugin_name for p in admin_plugins):
        return 'admin'
    elif any(p in plugin_name for p in optimization_plugins):
        return 'optimization'
    else:
        return 'other'

def download_from_modrinth(plugin_slug):
    """Stáhne nejnovější verzi pluginu z Modrinth a vrátí metadata"""
    try:
        # Krok 1: Získání informací o projektu
        project_resp = requests.get(f"https://api.modrinth.com/v2/project/{plugin_slug}")
        project_resp.raise_for_status()
        project_data = project_resp.json()
        
        # Získání dalších metadat
        project_id = project_data["id"]
        description = project_data.get("description", "No description available")
        author = "Unknown author"
        
        # Získání autora
        try:
            team_resp = requests.get(f"https://api.modrinth.com/v2/project/{plugin_slug}/members")
            if team_resp.status_code == 200:
                members = team_resp.json()
                if members:
                    author = members[0].get("user", {}).get("username", author)
        except Exception as e:
            log_error(f"Error getting team info for {plugin_slug}: {str(e)}")
        
        categories = project_data.get("categories", [])
        downloads = project_data.get("downloads", 0)
        updated_at = project_data.get("updated", datetime.now(timezone.utc).isoformat())
        
        log_message(f"🧩 Processing Modrinth project: {project_data['title']} ({project_id})")

        # Krok 2: Získání verzí projektu
        versions_resp = requests.get(f"https://api.modrinth.com/v2/project/{project_id}/version")
        versions_resp.raise_for_status()
        versions = versions_resp.json()

        if not versions:
            log_error(f"❌ No versions found for {plugin_slug}")
            return None, None, None

        latest_version = versions[0]
        log_message(f"⬇️  Latest version: {latest_version['version_number']}")

        # Krok 3: Získání URL k souboru
        files = latest_version["files"]
        for file in files:
            if file["primary"]:
                metadata = {
                    "title": project_data["title"],
                    "description": description,
                    "author": author,
                    "categories": categories,
                    "downloads": downloads,
                    "updated_at": updated_at,
                    "version_number": latest_version["version_number"],
                    "license": project_data.get("license", {}).get("name", "Unknown"),
                    "source_url": project_data.get("source_url"),
                    "issues_url": project_data.get("issues_url"),
                    "wiki_url": project_data.get("wiki_url"),
                    "donation_urls": project_data.get("donation_urls", []),
                    "gallery": project_data.get("gallery", [])
                }
                return file["url"], file["filename"], metadata
        
        log_error(f"❌ No primary file found for {plugin_slug}")
        return None, None, None

    except Exception as e:
        log_error(f"Error downloading from Modrinth for {plugin_slug}: {str(e)}")
        return None, None, None

def save_plugin_to_db(plugin_name, metadata, url, file_path):
    """Uloží informace o pluginu do databáze s využitím metadat z Modrinth"""
    try:
        version = metadata.get("version_number", extract_version_from_filename(plugin_name))
        
        updated_at = (datetime.fromisoformat(metadata["updated_at"]) 
                     if metadata.get("updated_at") 
                     else datetime.now(timezone.utc))
        
#        new_plugin = Plugin(
#           name=plugin_name,
#            display_name=metadata.get("title", get_plugin_display_name(plugin_name)),
#            description=metadata.get("description", f"Plugin {plugin_name} for Minecraft servers"),
#            version=version,
#            author=metadata.get("author", "Various Authors"),
#            file_path=file_path,
#            download_url=url,
#            plugin_type="core",
#            compatible_with="Folia",
#            category=determine_category_from_metadata(metadata, plugin_name),
#            created_at=datetime.now(timezone.utc),
#            updated_at=updated_at,
#            license=metadata.get("license"),
#            source_url=metadata.get("source_url"),
#            issues_url=metadata.get("issues_url"),
#            wiki_url=metadata.get("wiki_url"),
#            downloads_count=metadata.get("downloads", 0),
#            metadata_json=json.dumps(metadata)  # Uložíme celá metadata jako JSON string
#        )

        new_plugin = Plugin(
            name=plugin_name,
            display_name=get_plugin_display_name(plugin_name),
            description=metadata.get("description", f"Plugin {plugin_name} for Minecraft servers"),
            version=version,
            author=metadata.get("author", "Various Authors"),
            file_path=file_path,
            download_url=url,
            plugin_type="core",
            compatible_with="Folia",
            category=get_plugin_category(plugin_name),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.session.add(new_plugin)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        log_error(f"Failed to save {plugin_name} to database: {str(e)}")
        return False
    
def determine_category_from_metadata(metadata, plugin_name):
    """Určí kategorii pluginu na základě metadat a názvu"""
    if not metadata:
        return get_plugin_category(plugin_name.lower())
        
    categories = metadata.get("categories", [])
    plugin_name_lower = plugin_name.lower()
    
    # Nejprve zkusíme podle kategorií z Modrinth
    if "admin" in categories or "management" in categories:
        return "admin"
    elif "utility" in categories or "optimization" in categories:
        return "optimization"
    elif "security" in categories or "protection" in categories:
        return "protection"
    elif "economy" in categories:
        return "economy"
    
    # Pokud kategorie z Modrinth nepomohou, použijeme původní metodu
    return get_plugin_category(plugin_name_lower)

def save_manual_plugin_to_db(plugin_name, url, file_path):
    """Uloží manuální plugin do databáze"""
    try:
        version = extract_version_from_filename(os.path.basename(url))
        
#        new_plugin = Plugin(
#            name=plugin_name,
#            display_name=get_plugin_display_name(plugin_name),
#            description=f"Plugin {plugin_name} for Minecraft servers",
#            version=version,
#            author="Various Authors",
#            file_path=file_path,
#            download_url=url,
#            plugin_type="core",
#            compatible_with="Folia",
#            category=get_plugin_category(plugin_name.lower()),
#            created_at=datetime.now(timezone.utc),
#            updated_at=datetime.now(timezone.utc),
#            license="Unknown",
#           source_url=None,
#            issues_url=None,
#            wiki_url=None,
#            downloads_count=0,
#           metadata_json=json.dumps({})  # manuální plugin nemá metadata
#        )

        new_plugin = Plugin(
            name=plugin_name,
            display_name=get_plugin_display_name(plugin_name),
            description=f"Plugin {plugin_name} for Minecraft servers",
            version=version,
            author="Various Authors",
            file_path=file_path,
            download_url=url,
            plugin_type="core",
            compatible_with="Folia",
            category=get_plugin_category(plugin_name),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.session.add(new_plugin)
        db.session.commit()
        log_message(f"Successfully imported {plugin_name} v{version}")
        return True
    except Exception as e:
        db.session.rollback()
        log_error(f"Failed to save manual plugin {plugin_name} to database: {str(e)}")
        return False

def import_plugins():
    with app.app_context():
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        log_message("Starting plugin import process")
        
        # Stáhnout pluginy z Modrinth
        for plugin_slug in MODRINTH_PLUGINS:
            download_url, filename, metadata = download_from_modrinth(plugin_slug)
            if not download_url:
                continue
            
            plugin_name = os.path.splitext(filename)[0]
            temp_path = os.path.join(TEMP_DIR, filename)
            final_path = os.path.join(PLUGINS_DIR, filename)
            
            if Plugin.query.filter_by(name=plugin_name).first():
                log_message(f"Plugin {plugin_name} already exists, skipping")
                continue
            
            if download_file(download_url, temp_path):
                try:
                    os.replace(temp_path, final_path)
                    if save_plugin_to_db(plugin_name, metadata, download_url, final_path):
                        log_message(f"Successfully imported {metadata.get('title', plugin_name)}")
                    else:
                        log_error(f"Failed to save {plugin_name} to database")
                except Exception as e:
                    log_error(f"Failed to process {plugin_name}: {str(e)}")
        
        # Stáhnout manuální pluginy
        for url in MANUAL_PLUGIN_URLS:
            plugin_name = get_plugin_name_from_url(url)
            temp_path = os.path.join(TEMP_DIR, f"{plugin_name}.jar")
            final_path = os.path.join(PLUGINS_DIR, f"{plugin_name}.jar")
            
            log_message(f"Processing manual plugin {plugin_name} from {url}")
            
            # Kontrola existence v DB
            existing = Plugin.query.filter_by(name=plugin_name).first()
            if existing:
                log_message(f"Plugin {plugin_name} already exists, skipping")
                continue
            
            # Stáhnout do temp složky
            if download_file(url, temp_path):
                try:
                    # Přesunout do finálního umístění
                    os.replace(temp_path, final_path)
                    
                    # Uložit do databáze
                    if save_manual_plugin_to_db(plugin_name, url, final_path):
                        log_message(f"Successfully imported {plugin_name}")
                    else:
                        log_error(f"Failed to save {plugin_name} to database")
                except Exception as e:
                    log_error(f"Failed to process {plugin_name}: {str(e)}")
            else:
                log_error(f"Failed to download {plugin_name}")
        
        log_message("Plugin import process completed")

if __name__ == "__main__":
    import_plugins()