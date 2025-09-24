import os
import sys
import requests
import re
from datetime import datetime
from urllib.parse import urljoin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, BuildType, BuildVersion
from mc_server import BASE_BUILD_PATH

BUILD_NAME = "FORGE"
FORGE_PROMOTIONS_API = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/promotions_slim.json"
FORGE_MAVEN_REPO = "https://maven.minecraftforge.net/net/minecraftforge/forge/"

# 🔧 MANUÁLNĚ NASTAVENÁ MINIMÁLNÍ VERZE - ZMĚŇTE PODLE POTŘEBY
MIN_MINECRAFT_VERSION = "1.21"  # Pouze verze 1.18 a novější

def get_forge_versions():
    print("⏬ Načítám seznam Forge verzí...")
    print(f"🔧 Manuálně nastaveno: Stahuji pouze verze Minecraftu {MIN_MINECRAFT_VERSION} a novější")
    
    try:
        response = requests.get(FORGE_PROMOTIONS_API, timeout=15)
        response.raise_for_status()
        promotions = response.json().get("promos", {})

        versions = []
        pat = re.compile(r'^(?P<mc>[\d\.]+)-(recommended|latest)$')

        for key, build_version in promotions.items():
            m = pat.match(key)
            if not m:
                continue
            
            mc_version = m.group('mc')
            forge_version = str(build_version)

            # 🚨 FILTRACE PODLE MINIMÁLNÍ VERZE
            if not is_version_equal_or_newer(mc_version, MIN_MINECRAFT_VERSION):
                continue

            artifact_path = f"{mc_version}-{forge_version}/forge-{mc_version}-{forge_version}-installer.jar"
            url = urljoin(FORGE_MAVEN_REPO, artifact_path)

            # 🔎 ověření, že installer existuje
            head = requests.head(url)
            if head.status_code == 404:
                print(f"⚠️  Přeskakuji {mc_version}-{forge_version}, installer není na Maven repo.")
                continue

            versions.append((mc_version, forge_version, url))

        print(f"🔢 Nalezeno {len(versions)} Forge verzí ({MIN_MINECRAFT_VERSION}+) dostupných na Maven repo.")
        return versions
    except Exception as e:
        print(f"❌ Chyba při načítání Forge verzí: {e}")
        return []

def is_version_equal_or_newer(version, min_version):
    """
    Porovnání verzí Minecraftu - zda je verze rovna nebo novější než min_version
    """
    try:
        v1_parts = list(map(int, version.split('.')))
        v2_parts = list(map(int, min_version.split('.')))
        
        # Doplnění na stejný počet částí
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        
        # Porovnání
        for i in range(max_len):
            if v1_parts[i] > v2_parts[i]:
                return True
            elif v1_parts[i] < v2_parts[i]:
                return False
        return True  # Verze jsou stejné
    except ValueError:
        # Fallback pro nečíselné verze
        return version >= min_version

def ensure_build_type():
    build_type = BuildType.query.filter_by(name=BUILD_NAME).first()
    if not build_type:
        build_type = BuildType(name=BUILD_NAME, description="Forge server builds")
        db.session.add(build_type)
        db.session.commit()
        print("✅ BuildType FORGE vytvořen.")
    return build_type

def save_build_record_if_missing(mc_version, forge_version, url, build_type, file_path):
    exists = BuildVersion.query.filter_by(
        build_type=build_type,
        mc_version=mc_version,
        build_number=forge_version
    ).first()
    if exists:
        print(f"✔️  Forge {mc_version} build {forge_version} již v databázi existuje.")
        return

    build = BuildVersion(
        build_type=build_type,
        mc_version=mc_version,
        build_number=forge_version,
        download_url=url,
        file_path=file_path,
        created_at=datetime.utcnow()
    )
    db.session.add(build)
    db.session.commit()
    print(f"📄 Záznam pro Forge {mc_version} build {forge_version} přidán do databáze.")

def download_and_save_build(mc_version, forge_version, url, build_type):
    version_folder = f"{mc_version}-{forge_version}"
    version_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version_folder)
    os.makedirs(version_path, exist_ok=True)

    installer_path = os.path.join(version_path, "installer.jar")
    server_path = os.path.join(version_path, "server.jar")

    # Pokud už máme server.jar, nemusíme nic dělat
    if os.path.exists(server_path):
        print(f"📁 Server jar pro Forge {mc_version} build {forge_version} již existuje.")
        save_build_record_if_missing(mc_version, forge_version, url, build_type, server_path)
        return

    # Stáhnout installer
    print(f"⬇️  Stahuji {url} → {installer_path}")
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with open(installer_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Spustit installer pro vytvoření server.jar
    print(f"⚙️  Spouštím Forge installer...")
    import subprocess
    subprocess.run(["java", "-jar", installer_path, "--installServer"], cwd=version_path, check=True)

    # Zkontrolovat výsledek
    if not os.path.exists(server_path):
        # najít nejbližší forge-*-server.jar a přejmenovat
        for f in os.listdir(version_path):
            if f.startswith("forge-") and f.endswith(".jar"):
                os.rename(os.path.join(version_path, f), server_path)
                break

    if not os.path.exists(server_path):
        print(f"❌ Nepodařilo se najít Forge server.jar pro {mc_version}-{forge_version}")
        return

    print(f"✅ Forge server {mc_version}-{forge_version} připraven ({server_path}).")
    save_build_record_if_missing(mc_version, forge_version, url, build_type, server_path)

def run_sync():
    print("🚀 Spouštím synchronizaci FORGE buildů...")
    print(f"🎯 MANUÁLNÍ FILTR: Pouze verze Minecraftu {MIN_MINECRAFT_VERSION} a novější")
    
    versions = get_forge_versions()
    build_type = ensure_build_type()
    new_versions = []

    for mc_version, forge_version, url in versions:
        db_exists = BuildVersion.query.filter_by(
            build_type=build_type,
            mc_version=mc_version,
            build_number=forge_version
        ).first()

        version_folder = f"{mc_version}-{forge_version}"
        file_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version_folder, "installer.jar")
        file_exists = os.path.exists(file_path)

        if file_exists and db_exists:
            print(f"⏭️  Forge {mc_version} build {forge_version} již existuje (soubor + DB).")
            continue

        download_and_save_build(mc_version, forge_version, url, build_type)
        new_versions.append(f"{mc_version}-{forge_version}")

    if new_versions:
        message = f"Nalezeno {len(new_versions)} nových Forge buildů ({MIN_MINECRAFT_VERSION}+): {', '.join(new_versions)}"
        print(f"✅ {message}")
        return {"status": "success", "new_versions": new_versions, "message": message}
    else:
        message = f"Žádné nové Forge buildy ({MIN_MINECRAFT_VERSION}+) nebyly nalezeny."
        print(f"ℹ️  {message}")
        return {"status": "no_changes", "new_versions": [], "message": message}

if __name__ == "__main__":
    with app.app_context():
        run_sync()