import os
import sys
import requests
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, BuildType, BuildVersion
from mc_server import BASE_BUILD_PATH

BUILD_NAME = "PAPER"
PAPER_API = "https://api.papermc.io/v2/projects/paper"


def get_all_paper_builds():
    """Načte všechny verze a jejich nejnovější buildy z PaperMC API."""
    print("⏬ Načítám seznam Paper verzí...")
    response = requests.get(PAPER_API)
    response.raise_for_status()
    data = response.json()
    versions = data.get("versions", [])

    builds = []
    for version in versions:
        try:
            url = f"{PAPER_API}/versions/{version}"
            r = requests.get(url)
            r.raise_for_status()
            build_info = r.json()

            if not build_info.get("builds"):
                continue

            latest_build = max(build_info["builds"])
            download_url = (
                f"{PAPER_API}/versions/{version}/builds/{latest_build}/downloads/"
                f"paper-{version}-{latest_build}.jar"
            )
            builds.append((version, str(latest_build), download_url))
        except Exception as e:
            print(f"⚠️  Chyba při načítání buildů pro {version}: {e}")
            continue

    print(f"🔢 Celkem nalezeno {len(builds)} buildů Paper.")
    return builds


def ensure_build_type():
    build_type = BuildType.query.filter_by(name=BUILD_NAME).first()
    if not build_type:
        build_type = BuildType(name=BUILD_NAME, description="PaperMC server builds")
        db.session.add(build_type)
        db.session.commit()
        print("✅ BuildType PAPER vytvořen.")
    return build_type


def save_build_record_if_missing(mc_version, build_number, url, build_type, file_path):
    exists = BuildVersion.query.filter_by(
        build_type=build_type,
        mc_version=mc_version,
        build_number=build_number
    ).first()
    if exists:
        print(f"✔️  Paper {mc_version} build {build_number} již v databázi existuje.")
        return

    build = BuildVersion(
        build_type=build_type,
        mc_version=mc_version,
        build_number=build_number,
        download_url=url,
        file_path=file_path,
        created_at=datetime.utcnow()
    )
    db.session.add(build)
    db.session.commit()
    print(f"📄 Záznam pro Paper {mc_version} build {build_number} přidán do databáze.")


def download_and_save_build(mc_version, build_number, url, build_type):
    version_folder = f"{mc_version}-{build_number}"
    version_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version_folder)
    os.makedirs(version_path, exist_ok=True)
    file_path = os.path.join(version_path, "server.jar")

    if os.path.exists(file_path):
        print(f"📁 Soubor pro Paper {mc_version} build {build_number} již existuje.")
        save_build_record_if_missing(mc_version, build_number, url, build_type, file_path)
        return

    print(f"⬇️  Stahuji {url} → {file_path}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Chyba při stahování: {response.status_code}")
        return

    with open(file_path, "wb") as f:
        f.write(response.content)

    print(f"✅ Soubor {file_path} uložen.")
    save_build_record_if_missing(mc_version, build_number, url, build_type, file_path)


def run_sync():
    print("🚀 Spouštím synchronizaci PAPER buildů...")
    builds = get_all_paper_builds()
    build_type = ensure_build_type()
    new_versions = []

    for mc_version, build_number, url in builds:
        db_exists = BuildVersion.query.filter_by(
            build_type=build_type,
            mc_version=mc_version,
            build_number=build_number
        ).first()

        version_folder = f"{mc_version}-{build_number}"
        file_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version_folder, "server.jar")
        file_exists = os.path.exists(file_path)

        if file_exists and db_exists:
            print(f"⏭️  Paper {mc_version} build {build_number} již existuje (soubor + DB).")
            continue

        download_and_save_build(mc_version, build_number, url, build_type)
        new_versions.append(f"{mc_version}-{build_number}")

    if new_versions:
        message = f"Nalezeno {len(new_versions)} nových Paper buildů: {', '.join(new_versions)}"
        print(f"✅ {message}")
        return {"status": "success", "new_versions": new_versions, "message": message}
    else:
        message = "Žádné nové Paper buildy nebyly nalezeny."
        print(f"ℹ️  {message}")
        return {"status": "no_changes", "new_versions": [], "message": message}


if __name__ == "__main__":
    with app.app_context():
        run_sync()
