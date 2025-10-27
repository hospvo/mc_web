import os
from app import app, db
from models import Mod
from routes_mods import get_modrinth_info
from sqlalchemy.exc import SQLAlchemyError

def update_client_server_side():
    """Aktualizuje hodnoty client_side a server_side pro všechny mody v DB."""
    with app.app_context():
        mods = Mod.query.all()
        total = len(mods)
        print(f"🔍 Načteno {total} módů z databáze.\n")

        updated = 0
        for i, mod in enumerate(mods, start=1):
            slug = mod.name or mod.display_name
            if not slug:
                print(f"[{i}/{total}] ⚠️  Mod bez názvu – přeskočeno.")
                continue

            print(f"[{i}/{total}] {slug} ...", end=' ', flush=True)
            print(f"[{i}/{total}] {slug} ...", end=' ', flush=True)
            try:
                info = get_modrinth_info(slug)
                client_side = info.get("client_side")
                server_side = info.get("server_side")

                # aktualizace pouze pokud jsou hodnoty dostupné
                if client_side or server_side:
                    mod.client_side = client_side
                    mod.server_side = server_side
                    db.session.add(mod)
                    updated += 1
                    print(f"✅ {client_side}/{server_side}")
                else:
                    print("⚠️  žádná data z API")

            except Exception as e:
                print(f"❌ Chyba: {e}")

        try:
            db.session.commit()
            print(f"\n✅ Hotovo. Aktualizováno {updated}/{total} záznamů.")
        except SQLAlchemyError as e:
            db.session.rollback()
            print("\n❌ Chyba při ukládání do databáze:", e)

if __name__ == "__main__":
    # Inicializace Flask app pro získání kontextu
    with app.app_context():
        update_client_server_side()
