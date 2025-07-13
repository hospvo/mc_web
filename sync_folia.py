import os
import sys
import requests
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, BuildType, BuildVersion
from mc_server import BASE_BUILD_PATH

BUILD_NAME = "FOLIA"
GITHUB_API_RELEASES = "https://api.github.com/repos/neokoni/folia_build_action/releases"
PAST_RELEASE_API = "https://api.github.com/repos/neokoni/folia_build_action/releases/tags/Pastversions"


def get_all_folia_assets():
    """Spojí standardní snapshot releasy s těmi z Pastversions."""
    print("⏬ Načítám běžné releasy z GitHubu...")
    response = requests.get(GITHUB_API_RELEASES)
    response.raise_for_status()
    main_releases = response.json()

    print("⏬ Načítám Pastversions...")
    past_response = requests.get(PAST_RELEASE_API)
    past_response.raise_for_status()
    past_release = past_response.json()

    # Spoj všechny assets do jednoho seznamu
    all_assets = []
    for r in main_releases:
        all_assets.extend(r.get("assets", []))
    all_assets.extend(past_release.get("assets", []))

    print(f"🔢 Celkem nalezeno {len(all_assets)} assetů.")
    return all_assets



def extract_version_from_name(name):
    """Z názvu souboru vybere verzi Minecraftu (např. 1.21.3)."""
    parts = name.split("-")
    for part in parts:
        if part[0].isdigit() and "." in part:
            return part
    return None


def ensure_build_type():
    """Zajistí existenci build typu v databázi."""
    build_type = BuildType.query.filter_by(name=BUILD_NAME).first()
    if not build_type:
        build_type = BuildType(name=BUILD_NAME, description="Folia server builds")
        db.session.add(build_type)
        db.session.commit()
        print("✅ BuildType FOLIA vytvořen.")
    return build_type


def save_build_record_if_missing(version, url, build_type, file_path):
    """Pokud v DB není záznam o verzi, vytvoří ho."""
    exists = BuildVersion.query.filter_by(build_type=build_type, mc_version=version).first()
    if exists:
        print(f"✔️  Verze {version} již v databázi existuje.")
        return

    build = BuildVersion(
        build_type=build_type,
        mc_version=version,
        download_url=url,
        file_path=file_path,
        created_at=datetime.utcnow()
    )
    db.session.add(build)
    db.session.commit()
    print(f"📄 Záznam pro verzi {version} přidán do databáze.")


def download_and_save_build(version, url, build_type):
    version_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version)
    os.makedirs(version_path, exist_ok=True)
    file_path = os.path.join(version_path, "server.jar")

    if os.path.exists(file_path):
        print(f"📁 Soubor pro verzi {version} již existuje.")
        save_build_record_if_missing(version, url, build_type, file_path)
        return

    print(f"⬇️  Stahuji {url} → {file_path}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Chyba při stahování: {response.status_code}")
        return

    with open(file_path, "wb") as f:
        f.write(response.content)

    print(f"✅ Soubor {file_path} uložen.")
    save_build_record_if_missing(version, url, build_type, file_path)


def run_sync():
    print("🚀 Spouštím synchronizaci FOLIA buildů...")
    assets  = get_all_folia_assets()
    build_type = ensure_build_type()
    new_versions = []

    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        version = extract_version_from_name(name)

        if not version or not url:
            print(f"⚠️  Přeskočeno: {name}")
            continue

        version_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version)
        file_path = os.path.join(version_path, "server.jar")
        file_exists = os.path.exists(file_path)

        db_exists = BuildVersion.query.filter_by(build_type=build_type, mc_version=version).first()

        if file_exists and db_exists:
            print(f"⏭️  Verze {version} již existuje (soubor + DB).")
            continue

        download_and_save_build(version, url, build_type)
        new_versions.append(version)

    if new_versions:
        message = f"Nalezeno {len(new_versions)} nových verzí: {', '.join(new_versions)}"
        print(f"✅ {message}")
        return {
            "status": "success",
            "new_versions": new_versions,
            "message": message
        }
    else:
        message = "Žádné nové verze nebyly nalezeny."
        print(f"ℹ️  {message}")
        return {
            "status": "no_changes",
            "new_versions": [],
            "message": message
        }


if __name__ == "__main__":
    with app.app_context():
        run_sync()
