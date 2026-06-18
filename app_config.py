import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env_file(path=ENV_PATH):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def get_config_value(key, default=None):
    return os.environ.get(key, default)


def get_config_bool(key, default=False):
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_config_int(key, default):
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


_load_env_file()

SECRET_KEY = get_config_value("SECRET_KEY", "tajnyklic")
DATABASE_URI = get_config_value("DATABASE_URI", "sqlite:///db.sqlite3")

BASE_SERVERS_PATH = get_config_value(
    "BASE_SERVERS_PATH",
    r"C:\Users\hospv\Documents\minecraft_server"
)
BASE_PLUGIN_PATH = get_config_value(
    "BASE_PLUGIN_PATH",
    r"C:\Users\hospv\Documents\minecraft_plugins"
)
BASE_BUILD_PATH = get_config_value(
    "BASE_BUILD_PATH",
    r"C:\Users\hospv\Documents\minecraft_builds"
)
BASE_MODS_PATH = get_config_value(
    "BASE_MODS_PATH",
    r"C:\Users\hospv\Documents\minecraft_mods"
)

MINECRAFT_JAVA_PATH = get_config_value("MINECRAFT_JAVA_PATH", "java")
PORT_RANGE_START = get_config_int("PORT_RANGE_START", 25566)
PORT_RANGE_END = get_config_int("PORT_RANGE_END", 30000)
