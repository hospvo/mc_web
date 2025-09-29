import argparse
import os
from models import db, User, Plugin, Server, PluginConfig, PluginUpdateLog, server_plugins
from models import Mod, ModConfig, ModUpdateLog, server_mods  # PŘIDEJ tyto importy
from app import app

DB_PATH = os.path.join("instance", "app.db")

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
            "pluginupdatelog": PluginUpdateLog,
            # PŘIDEJ tyto modely pro módy:
            "mod": Mod,
            "modconfig": ModConfig,
            "modupdatelog": ModUpdateLog,
            "server_mods": "server_mods"  # speciální případ pro M:N tabulku
        }
        
        if table_name.lower() not in table_map:
            print(f"[ERR] Tabulka {table_name} není podporovaná.")
            print(f"Podporované tabulky: {', '.join(table_map.keys())}")
            return
        
        table = table_map[table_name.lower()]
        
        if table == "server_mods":
            # Speciální ošetření pro M:N tabulku
            db.session.execute(server_mods.delete())
        else:
            # Normální tabulka
            table.query.delete()
            
        db.session.commit()
    print(f"[OK] Tabulka {table_name} byla vymazána.")

def clear_all_mods():
    """Vymaže všechna data související s módy najednou."""
    with app.app_context():
        # Vymaž M:N vazby mezi servery a módy
        db.session.execute(server_mods.delete())
        # Vymaž logy modů
        ModUpdateLog.query.delete()
        # Vymaž konfigurace modů
        ModConfig.query.delete()
        # Vymaž módy
        Mod.query.delete()
        db.session.commit()
    print("[OK] Všechna data modů byla vymazána.")

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
    parser_table.add_argument("table", help="Název tabulky (např. user, plugin, server, mod, modconfig)")

    # 3) clear-mods
    subparsers.add_parser("clear-mods", help="Vymaže všechna data modů najednou")

    # 4) drop-db
    subparsers.add_parser("drop-db", help="Smaže celý databázový soubor")

    # 5) reset-db
    subparsers.add_parser("reset-db", help="Smaže databázi a vytvoří nové prázdné tabulky")

    args = parser.parse_args()

    if args.command == "clear-all":
        clear_all_data()
    elif args.command == "clear-table":
        clear_table(args.table)
    elif args.command == "clear-mods":
        clear_all_mods()
    elif args.command == "drop-db":
        drop_database()
    elif args.command == "reset-db":
        reset_database()

if __name__ == "__main__":
    main()