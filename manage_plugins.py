import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from app import app
from models import db, Plugin, PluginUpdateLog
from mc_server import BASE_PLUGIN_PATH


class PluginManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Správa pluginů")
        self.root.geometry("1000x600")

        # Notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1 - DB
        self.frame_db = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_db, text="Pluginy v DB")

        # Tab 2 - Disk
        self.frame_disk = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_disk, text="Pluginy na disku")

        # --- DB panel ---
        self.tree_db = ttk.Treeview(self.frame_db, columns=("id", "name", "display", "version", "file"), show="headings")
        self.tree_db.heading("id", text="ID")
        self.tree_db.heading("name", text="Name")
        self.tree_db.heading("display", text="Display")
        self.tree_db.heading("version", text="Version")
        self.tree_db.heading("file", text="File")
        self.tree_db.pack(fill=tk.BOTH, expand=True)

        btn_frame_db = ttk.Frame(self.frame_db)
        btn_frame_db.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_db, text="Obnovit", command=self.load_plugins_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_db, text="Smazat z DB", command=self.delete_from_db).pack(side=tk.LEFT, padx=5)

        # --- Disk panel ---
        self.tree_disk = ttk.Treeview(self.frame_disk, columns=("path", "file"), show="headings")
        self.tree_disk.heading("path", text="Path")
        self.tree_disk.heading("file", text="File")
        self.tree_disk.pack(fill=tk.BOTH, expand=True)

        btn_frame_disk = ttk.Frame(self.frame_disk)
        btn_frame_disk.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_disk, text="Obnovit", command=self.load_plugins_disk).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_disk, text="Smazat z disku", command=self.delete_from_disk).pack(side=tk.LEFT, padx=5)

        # Sirotci
        ttk.Button(root, text="Najít sirotky", command=self.find_orphans).pack(pady=5)

        # Načti při startu
        self.load_plugins_db()
        self.load_plugins_disk()

    def load_plugins_db(self):
        for row in self.tree_db.get_children():
            self.tree_db.delete(row)
        with app.app_context():
            plugins = Plugin.query.all()
            for p in plugins:
                self.tree_db.insert("", tk.END, values=(
                    p.id, p.name, p.display_name or "-", p.version, os.path.basename(p.file_path)
                ))

    def load_plugins_disk(self):
        for row in self.tree_disk.get_children():
            self.tree_disk.delete(row)
        for root, _, files in os.walk(os.path.join(BASE_PLUGIN_PATH, "plugins")):
            for f in files:
                if f.endswith(".jar"):
                    self.tree_disk.insert("", tk.END, values=(root, f))

    def delete_from_db(self):
        selection = self.tree_db.selection()  # 👈 oprav podle názvu tvého Treeview
        if not selection:
            messagebox.showwarning("Varování", "Vyberte plugin pro smazání z DB")
            return

        plugin_id = self.tree_db.item(selection[0])["values"][0]

        with app.app_context():
            plugin = Plugin.query.get(plugin_id)
            if not plugin:
                messagebox.showerror("Chyba", "Plugin nebyl nalezen v DB")
                return

            if messagebox.askyesno("Potvrzení", f"Opravdu chcete smazat plugin '{plugin.name}' z DB?"):
                try:
                    # Smažeme všechny logy pluginu
                    PluginUpdateLog.query.filter_by(plugin_id=plugin.id).delete()

                    # Smažeme plugin
                    db.session.delete(plugin)
                    db.session.commit()

                    self.load_plugins_db()
                    messagebox.showinfo("Hotovo", "Plugin + logy smazány z DB")
                except Exception as e:
                    db.session.rollback()
                    messagebox.showerror("Chyba", f"Nepodařilo se smazat plugin: {e}")


    def delete_from_disk(self):
        selected = self.tree_disk.selection()
        if not selected:
            messagebox.showwarning("Varování", "Vyberte plugin na disku")
            return

        path, file = self.tree_disk.item(selected[0])["values"]
        full_path = os.path.join(path, file)

        if not os.path.exists(full_path):
            messagebox.showerror("Chyba", "Soubor neexistuje")
            return

        if messagebox.askyesno("Potvrzení", f"Opravdu chcete přesunout '{file}' do backups?"):
            backup_dir = os.path.join(BASE_PLUGIN_PATH, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            new_name = os.path.join(backup_dir, file)
            shutil.move(full_path, new_name)
            self.load_plugins_disk()
            messagebox.showinfo("Hotovo", f"Soubor přesunut do {backup_dir}")

    def find_orphans(self):
        with app.app_context():
            db_files = {os.path.basename(p.file_path): p for p in Plugin.query.all()}
            disk_files = {}

            for root, _, files in os.walk(os.path.join(BASE_PLUGIN_PATH, "plugins")):
                for f in files:
                    if f.endswith(".jar"):
                        disk_files[f] = os.path.join(root, f)

            missing_files = [p for f, p in db_files.items() if f not in disk_files]
            extra_files = [path for f, path in disk_files.items() if f not in db_files]

            msg = []
            if missing_files:
                msg.append("V DB, ale chybí soubor:")
                for p in missing_files:
                    msg.append(f" - {p.id}: {p.name} ({p.version})")
            if extra_files:
                msg.append("Na disku, ale chybí v DB:")
                for path in extra_files:
                    msg.append(f" - {path}")

            if not msg:
                msg = ["Žádné sirotky nenalezeny"]

            messagebox.showinfo("Sirotci", "\n".join(msg))


if __name__ == "__main__":
    root = tk.Tk()
    gui = PluginManagerGUI(root)
    root.mainloop()
