import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json

from app import app
from models import db, Mod, ModUpdateLog
from mc_server import BASE_MODS_PATH


class ModManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Správa modů")
        self.root.geometry("1200x700")

        # Notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1 - DB
        self.frame_db = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_db, text="Módy v DB")

        # Tab 2 - Disk
        self.frame_disk = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_disk, text="Módy na disku")

        # --- DB panel ---
        columns_db = ("id", "name", "display", "version", "loader", "mc_version", "file")
        self.tree_db = ttk.Treeview(self.frame_db, columns=columns_db, show="headings")
        self.tree_db.heading("id", text="ID")
        self.tree_db.heading("name", text="Name")
        self.tree_db.heading("display", text="Display")
        self.tree_db.heading("version", text="Version")
        self.tree_db.heading("loader", text="Loader")
        self.tree_db.heading("mc_version", text="MC Version")
        self.tree_db.heading("file", text="File")
        
        # Nastavení šířky sloupců
        self.tree_db.column("id", width=50)
        self.tree_db.column("name", width=150)
        self.tree_db.column("display", width=150)
        self.tree_db.column("version", width=100)
        self.tree_db.column("loader", width=80)
        self.tree_db.column("mc_version", width=80)
        self.tree_db.column("file", width=200)
        
        self.tree_db.pack(fill=tk.BOTH, expand=True)

        # Scrollbar pro DB treeview
        scrollbar_db = ttk.Scrollbar(self.frame_db, orient=tk.VERTICAL, command=self.tree_db.yview)
        scrollbar_db.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_db.configure(yscrollcommand=scrollbar_db.set)

        btn_frame_db = ttk.Frame(self.frame_db)
        btn_frame_db.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_db, text="Obnovit", command=self.load_mods_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_db, text="Smazat z DB", command=self.delete_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_db, text="Zobrazit metadata", command=self.show_metadata).pack(side=tk.LEFT, padx=5)

        # --- Disk panel ---
        self.tree_disk = ttk.Treeview(self.frame_disk, columns=("path", "file", "size"), show="headings")
        self.tree_disk.heading("path", text="Path")
        self.tree_disk.heading("file", text="File")
        self.tree_disk.heading("size", text="Size (KB)")
        
        self.tree_disk.column("path", width=400)
        self.tree_disk.column("file", width=200)
        self.tree_disk.column("size", width=80)
        
        self.tree_disk.pack(fill=tk.BOTH, expand=True)

        # Scrollbar pro Disk treeview
        scrollbar_disk = ttk.Scrollbar(self.frame_disk, orient=tk.VERTICAL, command=self.tree_disk.yview)
        scrollbar_disk.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_disk.configure(yscrollcommand=scrollbar_disk.set)

        btn_frame_disk = ttk.Frame(self.frame_disk)
        btn_frame_disk.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_disk, text="Obnovit", command=self.load_mods_disk).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_disk, text="Smazat z disku", command=self.delete_from_disk).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_disk, text="Přidat do DB", command=self.add_to_db).pack(side=tk.LEFT, padx=5)

        # Sirotci a statistiky
        stats_frame = ttk.Frame(root)
        stats_frame.pack(fill=tk.X, pady=5)

        ttk.Button(stats_frame, text="Najít sirotky", command=self.find_orphans).pack(side=tk.LEFT, padx=5)
        ttk.Button(stats_frame, text="Statistiky", command=self.show_stats).pack(side=tk.LEFT, padx=5)

        # Načti při startu
        self.load_mods_db()
        self.load_mods_disk()

    def load_mods_db(self):
        for row in self.tree_db.get_children():
            self.tree_db.delete(row)
        with app.app_context():
            mods = Mod.query.all()
            for m in mods:
                self.tree_db.insert("", tk.END, values=(
                    m.id, 
                    m.name, 
                    m.display_name or "-", 
                    m.version, 
                    m.loader or "unknown",
                    m.minecraft_version or "unknown",
                    os.path.basename(m.file_path)
                ))

    def load_mods_disk(self):
        for row in self.tree_disk.get_children():
            self.tree_disk.delete(row)
        
        mods_dirs = [
            os.path.join(BASE_MODS_PATH, "mods", "core"),
            os.path.join(BASE_MODS_PATH, "mods", "optional"),
            os.path.join(BASE_MODS_PATH, "mods", "deprecated")
        ]
        
        for mods_dir in mods_dirs:
            if os.path.exists(mods_dir):
                for root, _, files in os.walk(mods_dir):
                    for f in files:
                        if f.endswith(".jar"):
                            full_path = os.path.join(root, f)
                            size_kb = os.path.getsize(full_path) // 1024
                            self.tree_disk.insert("", tk.END, values=(root, f, size_kb))

    def delete_from_db(self):
        selection = self.tree_db.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod pro smazání z DB")
            return

        mod_id = self.tree_db.item(selection[0])["values"][0]

        with app.app_context():
            mod = Mod.query.get(mod_id)
            if not mod:
                messagebox.showerror("Chyba", "Mod nebyl nalezen v DB")
                return

            if messagebox.askyesno("Potvrzení", f"Opravdu chcete smazat mod '{mod.display_name or mod.name}' z DB?\n\nToto smaže všechny záznamy o tomto modu včetně logů!"):
                try:
                    # Smažeme všechny logy modu
                    ModUpdateLog.query.filter_by(mod_id=mod.id).delete()
                    
                    # Smažeme konfigurace modu
                    from models import ModConfig
                    ModConfig.query.filter_by(mod_id=mod.id).delete()
                    
                    # Smažeme vazby na servery
                    from models import server_mods
                    db.session.execute(
                        server_mods.delete().where(server_mods.c.mod_id == mod.id)
                    )
                    
                    # Smažeme mod
                    db.session.delete(mod)
                    db.session.commit()

                    self.load_mods_db()
                    messagebox.showinfo("Hotovo", "Mod + logy + konfigurace smazány z DB")
                except Exception as e:
                    db.session.rollback()
                    messagebox.showerror("Chyba", f"Nepodařilo se smazat mod: {e}")

    def delete_from_disk(self):
        selection = self.tree_disk.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod na disku")
            return

        path, file, size = self.tree_disk.item(selection[0])["values"]
        full_path = os.path.join(path, file)

        if not os.path.exists(full_path):
            messagebox.showerror("Chyba", "Soubor neexistuje")
            return

        if messagebox.askyesno("Potvrzení", f"Opravdu chcete přesunout '{file}' do backups?"):
            backup_dir = os.path.join(BASE_MODS_PATH, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Vytvoříme unikátní název souboru
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = os.path.join(backup_dir, f"{timestamp}_{file}")
            
            try:
                shutil.move(full_path, new_name)
                self.load_mods_disk()
                messagebox.showinfo("Hotovo", f"Soubor přesunut do {backup_dir}")
            except Exception as e:
                messagebox.showerror("Chyba", f"Nepodařilo se přesunout soubor: {e}")

    def add_to_db(self):
        selection = self.tree_disk.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod na disku pro přidání do DB")
            return

        path, file, size = self.tree_disk.item(selection[0])["values"]
        full_path = os.path.join(path, file)

        # Dialog pro zadání metadat
        dialog = tk.Toplevel(self.root)
        dialog.title("Přidat mod do DB")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Název (slug):").pack(pady=5)
        name_entry = ttk.Entry(dialog, width=50)
        name_entry.pack(pady=5)
        name_entry.insert(0, os.path.splitext(file)[0])

        ttk.Label(dialog, text="Display name:").pack(pady=5)
        display_entry = ttk.Entry(dialog, width=50)
        display_entry.pack(pady=5)
        display_entry.insert(0, os.path.splitext(file)[0].replace('-', ' ').title())

        ttk.Label(dialog, text="Loader:").pack(pady=5)
        loader_combo = ttk.Combobox(dialog, values=["fabric", "forge", "neoforge", "quilt", "unknown"], state="readonly")
        loader_combo.pack(pady=5)
        loader_combo.set("unknown")

        ttk.Label(dialog, text="Minecraft verze:").pack(pady=5)
        mc_entry = ttk.Entry(dialog, width=50)
        mc_entry.pack(pady=5)
        mc_entry.insert(0, "1.20.1")

        def save_mod():
            name = name_entry.get().strip()
            display_name = display_entry.get().strip()
            loader = loader_combo.get()
            mc_version = mc_entry.get().strip()

            if not name:
                messagebox.showerror("Chyba", "Název je povinný")
                return

            with app.app_context():
                # Kontrola duplicity
                existing = Mod.query.filter_by(name=name).first()
                if existing:
                    messagebox.showerror("Chyba", f"Mod s názvem '{name}' již existuje v DB")
                    return

                try:
                    mod = Mod(
                        name=name,
                        display_name=display_name,
                        version="unknown",
                        author="unknown",
                        description="Manually added mod",
                        file_path=full_path,
                        download_url="",
                        source="manual",
                        category="unknown",
                        loader=loader,
                        minecraft_version=mc_version,
                        supported_loaders=json.dumps([loader] if loader != "unknown" else []),
                        minecraft_versions=json.dumps([mc_version] if mc_version else []),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.session.add(mod)
                    db.session.commit()

                    dialog.destroy()
                    self.load_mods_db()
                    messagebox.showinfo("Hotovo", f"Mod '{display_name}' přidán do DB")
                except Exception as e:
                    db.session.rollback()
                    messagebox.showerror("Chyba", f"Nepodařilo se přidat mod: {e}")

        ttk.Button(dialog, text="Uložit", command=save_mod).pack(pady=10)
        ttk.Button(dialog, text="Zrušit", command=dialog.destroy).pack(pady=5)

    def find_orphans(self):
        with app.app_context():
            db_files = {os.path.basename(p.file_path): p for p in Mod.query.all()}
            disk_files = {}

            # Prohledáme všechny mods složky
            mods_dirs = [
                os.path.join(BASE_MODS_PATH, "mods", "core"),
                os.path.join(BASE_MODS_PATH, "mods", "optional"),
                os.path.join(BASE_MODS_PATH, "mods", "deprecated")
            ]
            
            for mods_dir in mods_dirs:
                if os.path.exists(mods_dir):
                    for root, _, files in os.walk(mods_dir):
                        for f in files:
                            if f.endswith(".jar"):
                                disk_files[f] = os.path.join(root, f)

            missing_files = [p for f, p in db_files.items() if f not in disk_files]
            extra_files = [path for f, path in disk_files.items() if f not in db_files]

            msg = []
            if missing_files:
                msg.append("V DB, ale chybí soubor:")
                for p in missing_files:
                    msg.append(f" - {p.id}: {p.name} ({p.version}) - {os.path.basename(p.file_path)}")
            if extra_files:
                msg.append("Na disku, ale chybí v DB:")
                for path in extra_files:
                    msg.append(f" - {path}")

            if not msg:
                msg = ["Žádné sirotky nenalezeny"]

            messagebox.showinfo("Sirotci", "\n".join(msg))

    def show_metadata(self):
        selection = self.tree_db.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod z DB")
            return

        mod_id = self.tree_db.item(selection[0])["values"][0]

        with app.app_context():
            mod = Mod.query.get(mod_id)
            if not mod:
                messagebox.showerror("Chyba", "Mod nebyl nalezen")
                return

            # Dialog pro zobrazení metadat
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Metadata - {mod.display_name or mod.name}")
            dialog.geometry("500x400")
            dialog.transient(self.root)

            text_widget = tk.Text(dialog, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            metadata = {
                "ID": mod.id,
                "Name": mod.name,
                "Display Name": mod.display_name,
                "Version": mod.version,
                "Author": mod.author,
                "Loader": mod.loader,
                "Minecraft Version": mod.minecraft_version,
                "Category": mod.category,
                "Source": mod.source,
                "File Path": mod.file_path,
                "Download URL": mod.download_url,
                "Supported Loaders": json.loads(mod.supported_loaders) if mod.supported_loaders else [],
                "Minecraft Versions": json.loads(mod.minecraft_versions) if mod.minecraft_versions else [],
                "Created": mod.created_at,
                "Updated": mod.updated_at
            }

            for key, value in metadata.items():
                text_widget.insert(tk.END, f"{key}: {value}\n")

            text_widget.config(state=tk.DISABLED)

    def show_stats(self):
        with app.app_context():
            total_mods = Mod.query.count()
            loaders = db.session.query(Mod.loader, db.func.count(Mod.id)).group_by(Mod.loader).all()
            categories = db.session.query(Mod.category, db.func.count(Mod.id)).group_by(Mod.category).all()
            
            # Počty souborů na disku
            disk_count = 0
            mods_dirs = [
                os.path.join(BASE_MODS_PATH, "mods", "core"),
                os.path.join(BASE_MODS_PATH, "mods", "optional"),
                os.path.join(BASE_MODS_PATH, "mods", "deprecated")
            ]
            
            for mods_dir in mods_dirs:
                if os.path.exists(mods_dir):
                    for root, _, files in os.walk(mods_dir):
                        disk_count += len([f for f in files if f.endswith('.jar')])

            msg = [
                f"Celkem modů v DB: {total_mods}",
                f"Celkem souborů na disku: {disk_count}",
                "\nLoadery:"
            ]
            
            for loader, count in loaders:
                msg.append(f" - {loader or 'unknown'}: {count}")
                
            msg.append("\nKategorie:")
            for category, count in categories:
                msg.append(f" - {category or 'unknown'}: {count}")

            messagebox.showinfo("Statistiky modů", "\n".join(msg))


if __name__ == "__main__":
    root = tk.Tk()
    gui = ModManagerGUI(root)
    root.mainloop()