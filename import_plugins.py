import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
from models import db, Plugin
from app import app

# Konfigurace
BASE_PATH = r"C:\Users\hospv\Documents\minecraft_plugins"
PLUGINS_DIR = os.path.join(BASE_PATH, "plugins/core")
TEMP_DIR = os.path.join(BASE_PATH, "temp")
LOG_FILE = os.path.join(BASE_PATH, "plugin_import_log.txt")

# Seznam pluginů ke stažení (použijeme váš stávající seznam)
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
        f.write(f"[{datetime.now()}] {message}\n")

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

def import_plugins():
    with app.app_context():
        # Vytvoření potřebných adresářů
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        log_message("Starting plugin import process")
        
        for url in PLUGIN_URLS:
            plugin_name = get_plugin_name_from_url(url)
            temp_path = os.path.join(TEMP_DIR, f"{plugin_name}.jar")
            final_path = os.path.join(PLUGINS_DIR, f"{plugin_name}.jar")
            
            log_message(f"Processing {plugin_name} from {url}")
            
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
                    
                    # Extrahovat verzi
                    version = extract_version_from_filename(os.path.basename(url))
                    
                    # Vytvořit záznam v databázi
                    new_plugin = Plugin(
                        name=plugin_name,
                        display_name=get_plugin_display_name(plugin_name),
                        description=f"Plugin {plugin_name} for Minecraft servers",
                        version=version,
                        author="Various Authors",
                        file_path=final_path,
                        download_url=url,
                        plugin_type="core",
                        compatible_with="Folia",
                        category=get_plugin_category(plugin_name),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    db.session.add(new_plugin)
                    db.session.commit()
                    
                    log_message(f"Successfully imported {plugin_name} v{version}")
                except Exception as e:
                    db.session.rollback()
                    log_error(f"Failed to save {plugin_name} to database: {str(e)}")
            else:
                log_error(f"Failed to download {plugin_name}")
        
        log_message("Plugin import process completed")

if __name__ == "__main__":
    import_plugins()