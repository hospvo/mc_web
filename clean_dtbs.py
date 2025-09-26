import argparse
import os
from models import db, User, Plugin, Server, PluginConfig, PluginUpdateLog, server_plugins
from app import app   # importuj tvoji Flask aplikaci

DB_PATH = os.path.join("instance", "app.db")  # uprav podle cesty k SQLite

def clear_all_data():
    """Vymaže všechna data ze všech tabulek, ale ponechá strukturu."""
    with app.app_context():
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
    print("[OK] Všechna data byla vymazána, tabulky zůstaly.")

def clear_table(table_name):
    """Vymaže data z konkrétní tabulky."""
    with app.app_context():
        table_map = {
            "user": User,
            "plugin": Plugin,
            "server": Server,
            "pluginconfig": PluginConfig,
            "pluginupdatelog": PluginUpdateLog
        }
        if table_name.lower() not in table_map:
            print(f"[ERR] Tabulka {table_name} není podporovaná.")
            return
        table_map[table_name.lower()].query.delete()
        db.session.commit()
    print(f"[OK] Tabulka {table_name} byla vymazána.")

def drop_database():
    """Smaže celý SQLite soubor."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[OK] Databáze {DB_PATH} byla smazána.")
    else:
        print(f"[ERR] Soubor {DB_PATH} neexistuje.")

def reset_database():
    """Smaže databázi a vytvoří čisté schéma tabulek."""
    drop_database()
    with app.app_context():
        db.create_all()
    print("[OK] Databáze byla znovu vytvořena s čistým schématem.")

def main():
    parser = argparse.ArgumentParser(description="Správa SQLite databáze projektu")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1) clear-all
    subparsers.add_parser("clear-all", help="Vymaže všechna data (ponechá strukturu tabulek)")

    # 2) clear-table
    parser_table = subparsers.add_parser("clear-table", help="Vymaže data z konkrétní tabulky")
    parser_table.add_argument("table", help="Název tabulky (např. user, plugin, server)")

    # 3) drop-db
    subparsers.add_parser("drop-db", help="Smaže celý databázový soubor")

    # 4) reset-db
    subparsers.add_parser("reset-db", help="Smaže databázi a vytvoří nové prázdné tabulky")

    args = parser.parse_args()

    if args.command == "clear-all":
        clear_all_data()
    elif args.command == "clear-table":
        clear_table(args.table)
    elif args.command == "drop-db":
        drop_database()
    elif args.command == "reset-db":
        reset_database()

if __name__ == "__main__":
    main()
