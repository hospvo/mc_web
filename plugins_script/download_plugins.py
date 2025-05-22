import os
import requests
import json
from datetime import datetime
from urllib.parse import urlparse

# Konfigurace
#BASE_PATH = r"D:\\minecraft_plugins"
BASE_PATH = r"C:\Users\hospv\Documents\minecraft_plugins"
PLUGINS_DIR = os.path.join(BASE_PATH, "plugins/core")
TEMP_DIR = os.path.join(BASE_PATH, "temp")
DB_FILE = os.path.join(BASE_PATH, "plugins_db.json")
LOG_FILE = os.path.join(BASE_PATH, "update_log.txt")

# Seznam pluginů ke stažení (příklad - nahraďte skutečnými URL)
PLUGIN_URLS = [
    "https://cdn.modrinth.com/data/xss83sOY/versions/kqYQ5BbN/AdvancedServerList-Paper-5.5.1.jar",
    "https://cdn.modrinth.com/data/HFTnFHKn/versions/2sqMaMOJ/AntiPopup-11.jar",
    "https://www.spigotmc.org/resources/betterboard.96393/download?version=577015",
    "https://github.com/BetterGUI-MC/BetterGUI/releases/download/10.2/bettergui-10.2-shaded.jar",
    "https://github.com/BlueMap-Minecraft/BlueMap/releases/download/v5.7/bluemap-5.7-paper.jar",
    "https://github.com/DiscordSRV/DiscordSRV/releases/download/v1.29.0/DiscordSRV-Build-1.29.0.jar",
    "https://github.com/FancyMcPlugins/FancyHolograms/releases/download/v2.4.2/FancyHolograms-2.4.2.jar",
    "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot",
    "https://github.com/SkinsRestorer/SkinsRestorer/releases/download/15.6.3/SkinsRestorer.jar",
    "https://cdn.modrinth.com/data/3IEZ9vol/versions/oezVemzR/AuthMe-5.7.0-FORK-Universal.jar",
    "https://cdn.modrinth.com/data/EeyAn23L/versions/Zhcyw48Q/FancyNpcs-2.5.0.jar",
    "https://cdn.modrinth.com/data/fALzjamp/versions/SmZRkQyR/Chunky-Bukkit-1.4.36.jar",
    # Přidejte další pluginy
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
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {message}\n")

def log_error(message):
    """Zaznamená chybu do logu"""
    log_message(f"ERROR: {message}")

def update_database(plugin_data):
    """Aktualizuje databázi pluginů"""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                db = json.load(f)
        else:
            db = {"plugins": []}
        
        # Najdi nebo přidej plugin
        existing = next((p for p in db["plugins"] if p["name"] == plugin_data["name"]), None)
        if existing:
            existing.update(plugin_data)
        else:
            db["plugins"].append(plugin_data)
        
        with open(DB_FILE, 'w') as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        log_error(f"Database update failed: {str(e)}")

def get_plugin_name_from_url(url):
    """Získání názvu pluginů z URL"""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    return os.path.splitext(filename)[0]

def download_all_plugins():
    """Hlavní funkce pro stahování pluginů"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(PLUGINS_DIR, exist_ok=True)
    
    log_message("Starting plugin download process")
    
    for url in PLUGIN_URLS:
        plugin_name = get_plugin_name_from_url(url)
        temp_path = os.path.join(TEMP_DIR, f"{plugin_name}.jar")
        final_path = os.path.join(PLUGINS_DIR, f"{plugin_name}.jar")
        
        log_message(f"Processing {plugin_name} from {url}")
        
        # Stáhnout do temp složky
        if download_file(url, temp_path):
            # Přesunout do finálního umístění
            os.replace(temp_path, final_path)
            
            # Aktualizovat databázi
            plugin_data = {
                "name": plugin_name,
                "version": "1.0.0",  # Lze získat z názvu souboru nebo metadata
                "url": url,
                "path": final_path,
                "last_updated": str(datetime.now()),
                "status": "active"
            }
            update_database(plugin_data)
            
            log_message(f"Successfully installed {plugin_name}")
    
    log_message("Download process completed")

if __name__ == "__main__":
    download_all_plugins()