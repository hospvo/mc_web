from app import app
from models import db, Plugin, PluginUpdateLog

def delete_imported_plugins():
    with app.app_context():
        # Najdi pluginy, které chceme smazat
        plugins_to_delete = Plugin.query.filter_by(
            plugin_type="optional",
        ).all()

        plugin_ids = [plugin.id for plugin in plugins_to_delete]

        # Smaž napřed související záznamy v plugin_update_log
        if plugin_ids:
            deleted_logs = PluginUpdateLog.query.filter(PluginUpdateLog.plugin_id.in_(plugin_ids)).delete(synchronize_session=False)
            print(f"🧹 Smazáno {deleted_logs} záznamů z plugin_update_log.")

            # Smaž samotné pluginy
            deleted_plugins = 0
            for plugin in plugins_to_delete:
                db.session.delete(plugin)
                deleted_plugins += 1

            db.session.commit()
            print(f"✅ Smazáno {deleted_plugins} pluginů z plugin tabulky.")
        else:
            print("Žádné pluginy ke smazání.")

if __name__ == "__main__":
    delete_imported_plugins()
