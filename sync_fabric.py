import os
import sys
import requests
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, BuildType, BuildVersion
from mc_server import BASE_BUILD_PATH

BUILD_NAME = "FABRIC"
FABRIC_META_API = "https://meta.fabricmc.net/v2/versions"


def get_all_fabric_builds():
    """Načte kombinace Minecraft + Fabric loader + installer a vrátí seznam buildů."""
    print("⏬ Načítám seznam Fabric verzí...")

    try:
        # stabilní MC verze
        mc_resp = requests.get(f"{FABRIC_META_API}/game", timeout=15)
        mc_resp.raise_for_status()
        mc_versions = [v["version"] for v in mc_resp.json() if v.get("stable")]

        # nejnovější installer
        installer_resp = requests.get(f"{FABRIC_META_API}/installer", timeout=15)
        installer_resp.raise_for_status()
        installer_versions = installer_resp.json()
        latest_installer = installer_versions[0]["version"] if installer_versions else None
        if not latest_installer:
            print("❌ Nepodařilo se načíst installer verzi.")
            return []

        builds = []
        for mc_version in mc_versions:
            try:
                loader_resp = requests.get(f"{FABRIC_META_API}/loader/{mc_version}", timeout=15)
                if loader_resp.status_code != 200:
                    continue
                loader_data = loader_resp.json()
                if not loader_data:
                    continue

                # vezmeme první (nejnovější) loader
                loader_version = loader_data[0]["loader"]["version"]

                # složíme link na server.jar
                download_url = (
                    f"{FABRIC_META_API}/loader/{mc_version}/{loader_version}/{latest_installer}/server/jar"
                )
                builds.append((mc_version, loader_version, download_url))
            except Exception as e:
                print(f"⚠️  Chyba pro {mc_version}: {e}")
                continue

        print(f"🔢 Celkem nalezeno {len(builds)} buildů Fabric.")
        return builds

    except Exception as e:
        print(f"❌ Chyba při načítání Fabric verzí: {e}")
        return []


def ensure_build_type():
    build_type = BuildType.query.filter_by(name=BUILD_NAME).first()
    if not build_type:
        build_type = BuildType(name=BUILD_NAME, description="Fabric server builds")
        db.session.add(build_type)
        db.session.commit()
        print("✅ BuildType FABRIC vytvořen.")
    return build_type


def save_build_record_if_missing(mc_version, build_number, url, build_type, file_path):
    exists = BuildVersion.query.filter_by(
        build_type=build_type,
        mc_version=mc_version,
        build_number=build_number
    ).first()
    if exists:
        print(f"✔️  Fabric {mc_version} loader {build_number} už v DB je.")
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
    print(f"📄 Záznam pro Fabric {mc_version} loader {build_number} uložen do DB.")


def download_and_save_build(mc_version, build_number, url, build_type):
    version_folder = f"{mc_version}-{build_number}"
    version_path = os.path.join(BASE_BUILD_PATH, BUILD_NAME, "versions", version_folder)
    os.makedirs(version_path, exist_ok=True)
    file_path = os.path.join(version_path, "server.jar")

    if os.path.exists(file_path):
        print(f"📁 Fabric {mc_version} loader {build_number}: server.jar už existuje.")
        save_build_record_if_missing(mc_version, build_number, url, build_type, file_path)
        return

    print(f"⬇️  Stahuji {url} → {file_path}")
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        print(f"❌ Chyba při stahování: {r.status_code}")
        return

    with open(file_path, "wb") as f:
        f.write(r.content)

    print(f"✅ Uloženo {file_path}")
    save_build_record_if_missing(mc_version, build_number, url, build_type, file_path)


def run_sync():
    print("🚀 Spouštím synchronizaci FABRIC buildů...")
    builds = get_all_fabric_builds()
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
            print(f"⏭️  Fabric {mc_version}-{build_number} už existuje (soubor + DB).")
            continue

        download_and_save_build(mc_version, build_number, url, build_type)
        new_versions.append(f"{mc_version}-{build_number}")

    if new_versions:
        msg = f"Nalezeno {len(new_versions)} nových Fabric buildů: {', '.join(new_versions)}"
        print(f"✅ {msg}")
        return {"status": "success", "new_versions": new_versions, "message": msg}
    else:
        msg = "Žádné nové Fabric buildy nebyly nalezeny."
        print(f"ℹ️  {msg}")
        return {"status": "no_changes", "new_versions": [], "message": msg}


if __name__ == "__main__":
    with app.app_context():
        run_sync()
