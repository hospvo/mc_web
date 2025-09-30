import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json
import sys

# Přidání cesty pro importy
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, Mod, ModUpdateLog, Plugin, PluginUpdateLog, BuildType, BuildVersion
from mc_server import BASE_MODS_PATH, BASE_PLUGIN_PATH, BASE_BUILD_PATH


class IntegratedManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Integrovaný správce Minecraft serverů")
        self.root.geometry("1400x800")

        # Hlavní notebook (záložky)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1 - Módy
        self.frame_mods = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_mods, text="Správa modů")

        # Tab 2 - Pluginy
        self.frame_plugins = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_plugins, text="Správa pluginů")

        # Tab 3 - Buildy
        self.frame_builds = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_builds, text="Správa buildů")

        # Tab 4 - Statistiky
        self.frame_stats = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_stats, text="Statistiky a nástroje")

        # Inicializace jednotlivých částí
        self.setup_mods_tab()
        self.setup_plugins_tab()
        self.setup_builds_tab()
        self.setup_stats_tab()

        # Načtení dat při startu
        self.load_all_data()

    def setup_mods_tab(self):
        """Nastavení záložky pro správu modů"""
        # Notebook pro módy
        mods_notebook = ttk.Notebook(self.frame_mods)
        mods_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-tab: Módy v DB
        frame_mods_db = ttk.Frame(mods_notebook)
        mods_notebook.add(frame_mods_db, text="Módy v databázi")

        # Sub-tab: Módy na disku
        frame_mods_disk = ttk.Frame(mods_notebook)
        mods_notebook.add(frame_mods_disk, text="Módy na disku")

        # --- DB mods panel ---
        columns_db = ("id", "name", "display", "version", "loader", "mc_version", "file")
        self.tree_mods_db = ttk.Treeview(frame_mods_db, columns=columns_db, show="headings")
        
        # Nastavení hlaviček
        headings = [
            ("id", "ID", 50),
            ("name", "Name", 150),
            ("display", "Display", 150),
            ("version", "Version", 100),
            ("loader", "Loader", 80),
            ("mc_version", "MC Version", 80),
            ("file", "File", 200)
        ]
        
        for col, text, width in headings:
            self.tree_mods_db.heading(col, text=text)
            self.tree_mods_db.column(col, width=width)
        
        self.tree_mods_db.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar pro DB mods
        scrollbar_db = ttk.Scrollbar(frame_mods_db, orient=tk.VERTICAL, command=self.tree_mods_db.yview)
        scrollbar_db.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_mods_db.configure(yscrollcommand=scrollbar_db.set)

        # Tlačítka pro DB mods
        btn_frame_db = ttk.Frame(frame_mods_db)
        btn_frame_db.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_db, text="Obnovit", command=self.load_mods_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_db, text="Smazat z DB", command=self.delete_mod_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_db, text="Zobrazit metadata", command=self.show_mod_metadata).pack(side=tk.LEFT, padx=5)

        # --- Disk mods panel ---
        self.tree_mods_disk = ttk.Treeview(frame_mods_disk, columns=("path", "file", "size"), show="headings")
        
        disk_headings = [
            ("path", "Path", 400),
            ("file", "File", 200),
            ("size", "Size (KB)", 80)
        ]
        
        for col, text, width in disk_headings:
            self.tree_mods_disk.heading(col, text=text)
            self.tree_mods_disk.column(col, width=width)
        
        self.tree_mods_disk.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar pro Disk mods
        scrollbar_disk = ttk.Scrollbar(frame_mods_disk, orient=tk.VERTICAL, command=self.tree_mods_disk.yview)
        scrollbar_disk.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_mods_disk.configure(yscrollcommand=scrollbar_disk.set)

        # Tlačítka pro Disk mods
        btn_frame_disk = ttk.Frame(frame_mods_disk)
        btn_frame_disk.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_disk, text="Obnovit", command=self.load_mods_disk).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_disk, text="Smazat z disku", command=self.delete_mod_from_disk).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_disk, text="Přidat do DB", command=self.add_mod_to_db).pack(side=tk.LEFT, padx=5)

    def setup_plugins_tab(self):
        """Nastavení záložky pro správu pluginů"""
        # Notebook pro pluginy
        plugins_notebook = ttk.Notebook(self.frame_plugins)
        plugins_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-tab: Pluginy v DB
        frame_plugins_db = ttk.Frame(plugins_notebook)
        plugins_notebook.add(frame_plugins_db, text="Pluginy v databázi")

        # Sub-tab: Pluginy na disku
        frame_plugins_disk = ttk.Frame(plugins_notebook)
        plugins_notebook.add(frame_plugins_disk, text="Pluginy na disku")

        # --- DB plugins panel ---
        self.tree_plugins_db = ttk.Treeview(frame_plugins_db, columns=("id", "name", "display", "version", "file"), show="headings")
        
        plugin_headings = [
            ("id", "ID", 50),
            ("name", "Name", 150),
            ("display", "Display", 150),
            ("version", "Version", 100),
            ("file", "File", 250)
        ]
        
        for col, text, width in plugin_headings:
            self.tree_plugins_db.heading(col, text=text)
            self.tree_plugins_db.column(col, width=width)
        
        self.tree_plugins_db.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tlačítka pro DB plugins
        btn_frame_db = ttk.Frame(frame_plugins_db)
        btn_frame_db.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_db, text="Obnovit", command=self.load_plugins_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_db, text="Smazat z DB", command=self.delete_plugin_from_db).pack(side=tk.LEFT, padx=5)

        # --- Disk plugins panel ---
        self.tree_plugins_disk = ttk.Treeview(frame_plugins_disk, columns=("path", "file"), show="headings")
        
        self.tree_plugins_disk.heading("path", text="Path")
        self.tree_plugins_disk.heading("file", text="File")
        self.tree_plugins_disk.column("path", width=400)
        self.tree_plugins_disk.column("file", width=200)
        
        self.tree_plugins_disk.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tlačítka pro Disk plugins
        btn_frame_disk = ttk.Frame(frame_plugins_disk)
        btn_frame_disk.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame_disk, text="Obnovit", command=self.load_plugins_disk).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_disk, text="Smazat z disku", command=self.delete_plugin_from_disk).pack(side=tk.LEFT, padx=5)

    def setup_builds_tab(self):
        """Nastavení záložky pro správu buildů"""
        main_frame = ttk.Frame(self.frame_builds)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dropdown pro BuildType
        ttk.Label(main_frame, text="Typ buildu:").pack(anchor=tk.W, pady=(0, 5))
        self.build_type_var = tk.StringVar()
        self.build_type_dropdown = ttk.Combobox(main_frame, textvariable=self.build_type_var, state="readonly")
        self.build_type_dropdown.pack(fill=tk.X, pady=(0, 10))
        self.build_type_dropdown.bind("<<ComboboxSelected>>", lambda e: self.refresh_builds())

        # Seznam buildů
        self.tree_builds = ttk.Treeview(main_frame, columns=("mc_version", "build_number", "file_path"), show="headings")
        
        build_headings = [
            ("mc_version", "MC verze", 100),
            ("build_number", "Build číslo", 100),
            ("file_path", "Cesta k souboru", 400)
        ]
        
        for col, text, width in build_headings:
            self.tree_builds.heading(col, text=text)
            self.tree_builds.column(col, width=width)
        
        self.tree_builds.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Tlačítka pro správu buildů
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Obnovit", command=self.refresh_builds).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Smazat vybraný", command=self.delete_selected_build).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Smazat všechny tohoto typu", command=self.delete_all_builds_of_type).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Smazat všechny buildy", command=self.delete_all_builds).pack(side=tk.LEFT, padx=5)

    def setup_stats_tab(self):
        """Nastavení záložky pro statistiky a nástroje"""
        main_frame = ttk.Frame(self.frame_stats)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Sekce pro nástroje
        tools_frame = ttk.LabelFrame(main_frame, text="Nástroje pro správu")
        tools_frame.pack(fill=tk.X, pady=(0, 10))

        # Tlačítka pro nástroje
        ttk.Button(tools_frame, text="Najít sirotky (modů)", command=self.find_mod_orphans).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(tools_frame, text="Najít sirotky (pluginů)", command=self.find_plugin_orphans).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(tools_frame, text="Statistiky modů", command=self.show_mod_stats).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(tools_frame, text="Statistiky pluginů", command=self.show_plugin_stats).pack(side=tk.LEFT, padx=5, pady=5)

        # Sekce pro statistiky
        stats_frame = ttk.LabelFrame(main_frame, text="Rychlé statistiky")
        stats_frame.pack(fill=tk.BOTH, expand=True)

        # Textové pole pro statistiky
        self.stats_text = tk.Text(stats_frame, wrap=tk.WORD, height=15)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.stats_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stats_text.configure(yscrollcommand=scrollbar.set)

        # Tlačítko pro aktualizaci statistik
        ttk.Button(stats_frame, text="Aktualizovat statistiky", command=self.update_quick_stats).pack(pady=5)

    def load_all_data(self):
        """Načte všechna data při startu"""
        self.load_mods_db()
        self.load_mods_disk()
        self.load_plugins_db()
        self.load_plugins_disk()
        self.load_build_types()
        self.update_quick_stats()

    # === MODS FUNCTIONS ===
    def load_mods_db(self):
        """Načte módy z databáze"""
        for row in self.tree_mods_db.get_children():
            self.tree_mods_db.delete(row)
        
        with app.app_context():
            mods = Mod.query.all()
            for m in mods:
                self.tree_mods_db.insert("", tk.END, values=(
                    m.id, 
                    m.name, 
                    m.display_name or "-", 
                    m.version, 
                    m.loader or "unknown",
                    m.minecraft_version or "unknown",
                    os.path.basename(m.file_path)
                ))

    def load_mods_disk(self):
        """Načte módy z disku"""
        for row in self.tree_mods_disk.get_children():
            self.tree_mods_disk.delete(row)
        
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
                            self.tree_mods_disk.insert("", tk.END, values=(root, f, size_kb))

    def delete_mod_from_db(self):
        """Smaže mod z databáze"""
        selection = self.tree_mods_db.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod pro smazání z DB")
            return

        mod_id = self.tree_mods_db.item(selection[0])["values"][0]

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

    def delete_mod_from_disk(self):
        """Smaže mod z disku (přesune do backups)"""
        selection = self.tree_mods_disk.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod na disku")
            return

        path, file, size = self.tree_mods_disk.item(selection[0])["values"]
        full_path = os.path.join(path, file)

        if not os.path.exists(full_path):
            messagebox.showerror("Chyba", "Soubor neexistuje")
            return

        if messagebox.askyesno("Potvrzení", f"Opravdu chcete přesunout '{file}' do backups?"):
            backup_dir = os.path.join(BASE_MODS_PATH, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = os.path.join(backup_dir, f"{timestamp}_{file}")
            
            try:
                shutil.move(full_path, new_name)
                self.load_mods_disk()
                messagebox.showinfo("Hotovo", f"Soubor přesunut do {backup_dir}")
            except Exception as e:
                messagebox.showerror("Chyba", f"Nepodařilo se přesunout soubor: {e}")

    def add_mod_to_db(self):
        """Přidá mod z disku do databáze"""
        selection = self.tree_mods_disk.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod na disku pro přidání do DB")
            return

        path, file, size = self.tree_mods_disk.item(selection[0])["values"]
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

    def show_mod_metadata(self):
        """Zobrazí metadata modu"""
        selection = self.tree_mods_db.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte mod z DB")
            return

        mod_id = self.tree_mods_db.item(selection[0])["values"][0]

        with app.app_context():
            mod = Mod.query.get(mod_id)
            if not mod:
                messagebox.showerror("Chyba", "Mod nebyl nalezen")
                return

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

    # === PLUGINS FUNCTIONS ===
    def load_plugins_db(self):
        """Načte pluginy z databáze"""
        for row in self.tree_plugins_db.get_children():
            self.tree_plugins_db.delete(row)
        
        with app.app_context():
            plugins = Plugin.query.all()
            for p in plugins:
                self.tree_plugins_db.insert("", tk.END, values=(
                    p.id, p.name, p.display_name or "-", p.version, os.path.basename(p.file_path)
                ))

    def load_plugins_disk(self):
        """Načte pluginy z disku"""
        for row in self.tree_plugins_disk.get_children():
            self.tree_plugins_disk.delete(row)
        
        for root, _, files in os.walk(os.path.join(BASE_PLUGIN_PATH, "plugins")):
            for f in files:
                if f.endswith(".jar"):
                    self.tree_plugins_disk.insert("", tk.END, values=(root, f))

    def delete_plugin_from_db(self):
        """Smaže plugin z databáze"""
        selection = self.tree_plugins_db.selection()
        if not selection:
            messagebox.showwarning("Varování", "Vyberte plugin pro smazání z DB")
            return

        plugin_id = self.tree_plugins_db.item(selection[0])["values"][0]

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

    def delete_plugin_from_disk(self):
        """Smaže plugin z disku (přesune do backups)"""
        selected = self.tree_plugins_disk.selection()
        if not selected:
            messagebox.showwarning("Varování", "Vyberte plugin na disku")
            return

        path, file = self.tree_plugins_disk.item(selected[0])["values"]
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

    # === BUILDS FUNCTIONS ===
    def load_build_types(self):
        """Načte typy buildů do dropdownu"""
        with app.app_context():
            types = BuildType.query.all()
            self.build_type_dropdown["values"] = [t.name for t in types]
            if types:
                self.build_type_var.set(types[0].name)
                self.refresh_builds()

    def refresh_builds(self):
        """Načte seznam buildů pro vybraný BuildType"""
        self.tree_builds.delete(*self.tree_builds.get_children())
        selected_type = self.build_type_var.get()
        if not selected_type:
            return

        with app.app_context():
            build_type = BuildType.query.filter_by(name=selected_type).first()
            if not build_type:
                return
            builds = BuildVersion.query.filter_by(build_type=build_type).all()

            for b in builds:
                self.tree_builds.insert("", "end", iid=b.id, values=(b.mc_version, b.build_number, b.file_path))

    def delete_selected_build(self):
        """Smaže vybraný build"""
        selected = self.tree_builds.selection()
        if not selected:
            messagebox.showwarning("Upozornění", "Musíte vybrat build k odstranění.")
            return

        build_id = int(selected[0])
        with app.app_context():
            build = BuildVersion.query.get(build_id)
            if build:
                db.session.delete(build)
                db.session.commit()
                messagebox.showinfo("Hotovo", f"Build {build.mc_version}-{build.build_number} byl odstraněn.")
        self.refresh_builds()

    def delete_all_builds_of_type(self):
        """Smaže všechny buildy vybraného typu"""
        selected_type = self.build_type_var.get()
        if not selected_type:
            return

        if not messagebox.askyesno("Potvrzení", f"Opravdu chcete smazat všechny buildy typu {selected_type}?"):
            return

        with app.app_context():
            build_type = BuildType.query.filter_by(name=selected_type).first()
            if build_type:
                BuildVersion.query.filter_by(build_type=build_type).delete()
                db.session.commit()
        self.refresh_builds()

    def delete_all_builds(self):
        """Smaže všechny buildy v databázi"""
        if not messagebox.askyesno("Potvrzení", "Opravdu chcete smazat všechny buildy (všechny typy)?"):
            return

        with app.app_context():
            BuildVersion.query.delete()
            db.session.commit()
        self.refresh_builds()

    # === STATISTICS AND TOOLS FUNCTIONS ===
    def find_mod_orphans(self):
        """Najde sirotky modů"""
        with app.app_context():
            db_files = {os.path.basename(p.file_path): p for p in Mod.query.all()}
            disk_files = {}

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

            messagebox.showinfo("Sirotky modů", "\n".join(msg))

    def find_plugin_orphans(self):
        """Najde sirotky pluginů"""
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

            messagebox.showinfo("Sirotky pluginů", "\n".join(msg))

    def show_mod_stats(self):
        """Zobrazí statistiky modů"""
        with app.app_context():
            total_mods = Mod.query.count()
            loaders = db.session.query(Mod.loader, db.func.count(Mod.id)).group_by(Mod.loader).all()
            categories = db.session.query(Mod.category, db.func.count(Mod.id)).group_by(Mod.category).all()
            
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

    def show_plugin_stats(self):
        """Zobrazí statistiky pluginů"""
        with app.app_context():
            total_plugins = Plugin.query.count()
            categories = db.session.query(Plugin.category, db.func.count(Plugin.id)).group_by(Plugin.category).all()
            
            disk_count = 0
            plugins_dir = os.path.join(BASE_PLUGIN_PATH, "plugins")
            if os.path.exists(plugins_dir):
                for root, _, files in os.walk(plugins_dir):
                    disk_count += len([f for f in files if f.endswith('.jar')])

            msg = [
                f"Celkem pluginů v DB: {total_plugins}",
                f"Celkem souborů na disku: {disk_count}",
                "\nKategorie:"
            ]
            
            for category, count in categories:
                msg.append(f" - {category or 'unknown'}: {count}")

            messagebox.showinfo("Statistiky pluginů", "\n".join(msg))

    def update_quick_stats(self):
        """Aktualizuje rychlé statistiky"""
        with app.app_context():
            mods_count = Mod.query.count()
            plugins_count = Plugin.query.count()
            builds_count = BuildVersion.query.count()
            
            # Počty souborů na disku
            mods_disk = 0
            mods_dirs = [
                os.path.join(BASE_MODS_PATH, "mods", "core"),
                os.path.join(BASE_MODS_PATH, "mods", "optional"),
                os.path.join(BASE_MODS_PATH, "mods", "deprecated")
            ]
            
            for mods_dir in mods_dirs:
                if os.path.exists(mods_dir):
                    for root, _, files in os.walk(mods_dir):
                        mods_disk += len([f for f in files if f.endswith('.jar')])

            plugins_disk = 0
            plugins_dir = os.path.join(BASE_PLUGIN_PATH, "plugins")
            if os.path.exists(plugins_dir):
                for root, _, files in os.walk(plugins_dir):
                    plugins_disk += len([f for f in files if f.endswith('.jar')])

            stats_text = f"""=== RYCHLÉ STATISTIKY ===

MÓDY:
- V databázi: {mods_count}
- Na disku: {mods_disk}
- Rozdíl: {mods_disk - mods_count}

PLUGINY:
- V databázi: {plugins_count}
- Na disku: {plugins_disk}
- Rozdíl: {plugins_disk - plugins_count}

BUILDY:
- Celkem v DB: {builds_count}

=== POSLEDNÍ AKTIVITY ===

Poslední aktualizace modů:
"""

            # Posledních 5 aktualizací modů - použijeme timestamp místo updated_at
            try:
                last_mod_updates = ModUpdateLog.query.order_by(ModUpdateLog.timestamp.desc()).limit(5).all()
                for update in last_mod_updates:
                    mod = Mod.query.get(update.mod_id)
                    mod_name = mod.display_name or mod.name if mod else f"ID:{update.mod_id}"
                    version_info = f"{update.version_from} → {update.version_to}" if update.version_from and update.version_to else update.version_to or "unknown"
                    stats_text += f"- {mod_name}: {update.action} {version_info} ({update.timestamp.strftime('%Y-%m-%d %H:%M')})\n"
            except Exception as e:
                stats_text += f"- Chyba při načítání: {str(e)}\n"

            stats_text += "\nPoslední aktualizace pluginů:\n"
            
            # Posledních 5 aktualizací pluginů - použijeme timestamp
            try:
                last_plugin_updates = PluginUpdateLog.query.order_by(PluginUpdateLog.timestamp.desc()).limit(5).all()
                for update in last_plugin_updates:
                    plugin = Plugin.query.get(update.plugin_id)
                    plugin_name = plugin.display_name or plugin.name if plugin else f"ID:{update.plugin_id}"
                    version_info = f"{update.version_from} → {update.version_to}" if update.version_from and update.version_to else update.version_to or "unknown"
                    stats_text += f"- {plugin_name}: {update.action} {version_info} ({update.timestamp.strftime('%Y-%m-%d %H:%M')})\n"
            except Exception as e:
                stats_text += f"- Chyba při načítání: {str(e)}\n"

            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_text)


def main():
    root = tk.Tk()
    app = IntegratedManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()