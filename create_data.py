import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple
from models import db, User, Server, BuildType, BuildVersion
from server_configs import update_server_ports
from mc_server import BASE_SERVERS_PATH, BASE_BUILD_PATH

class ServerCreatorApp:
    def __init__(self, root: tk.Tk, flask_app):
        self.root = root
        self.flask_app = flask_app
        self.root.title("Minecraft Server Manager")
        self.root.resizable(False, False)

        # Inicializace UI prvků nejdříve
        self.version_var = tk.StringVar()
        self.version_dropdown = None
        
        # Načtení dat
        with self.flask_app.app_context():
            from models import User, BuildType, BuildVersion
            self.User = User
            self.BuildType = BuildType
            self.BuildVersion = BuildVersion
            self.users = self.load_users()
            self.builds = self.load_builds()
        
        self.setup_ui()
        self.center_window()
        
    def center_window(self):
        """Centruje okno na obrazovce"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')

    def load_users(self) -> List[User]:
        """Načte seznam uživatelů z databáze"""
        return User.query.order_by(User.username).all()

    def load_builds(self) -> Dict[str, List[str]]:
        """Načte dostupné buildy a verze ze souborového systému"""
        builds = {}
        if not os.path.exists(BASE_BUILD_PATH):
            return builds
            
        for build_name in sorted(os.listdir(BASE_BUILD_PATH)):
            build_path = os.path.join(BASE_BUILD_PATH, build_name, "versions")
            if os.path.isdir(build_path):
                versions = sorted([
                    v for v in os.listdir(build_path) 
                    if os.path.isdir(os.path.join(build_path, v))
                ], reverse=True)  # Seřazeno od nejnovější verze
                builds[build_name] = versions
        return builds

    def check_or_create_server_folder(self, server_name: str) -> bool:
        """Zkontroluje existenci složky serveru"""
        folder_path = os.path.join(BASE_SERVERS_PATH, server_name)
        if os.path.exists(folder_path):
            return True
            
        result = messagebox.askyesno(
            "Složka neexistuje", 
            f"Složka pro server '{server_name}' neexistuje.\n\nCesta: {folder_path}\n\nChcete ji vytvořit?",
            icon='question'
        )
        if result:
            try:
                os.makedirs(folder_path, exist_ok=True)
                return True
            except Exception as e:
                messagebox.showerror(
                    "Chyba", 
                    f"Nepodařilo se vytvořit složku:\n{str(e)}"
                )
                return False
        return False

    def validate_inputs(self) -> Tuple[bool, Optional[str]]:
        """Validace vstupních dat"""
        server_name = self.entry_name.get().strip()
        selected_user = self.user_var.get()
        service_level = self.service_var.get()
        build = self.build_var.get()
        version = self.version_var.get()

        if not all([server_name, selected_user, service_level, build, version]):
            return False, "Všechna pole jsou povinná."
            
        if not server_name.replace('_', '').isalnum():
            return False, "Název serveru může obsahovat pouze písmena, čísla a podtržítka."
            
        if len(server_name) > 32:
            return False, "Název serveru je příliš dlouhý (max 32 znaků)."
            
        return True, None

    def create_server(self):
        """Vytvoří nový server"""
        is_valid, error = self.validate_inputs()
        if not is_valid:
            messagebox.showerror("Chyba", error)
            return

        server_name = self.entry_name.get().strip()
        if not self.check_or_create_server_folder(server_name):
            return

        with self.flask_app.app_context():
            try:
                # Najít uživatele
                user = next(
                    (u for u in self.users 
                     if f"{u.username} <{u.email}>" == self.user_var.get()), 
                    None
                )
                if not user:
                    messagebox.showerror("Chyba", "Uživatel nenalezen.")
                    return

                # Najít build a verzi
                build_type = BuildType.query.filter_by(name=self.build_var.get()).first()
                build_version = BuildVersion.query.filter_by(
                    build_type=build_type, 
                    mc_version=self.version_var.get()
                ).first()

                if not build_type or not build_version:
                    messagebox.showerror("Chyba", "Build nebo verze nenalezena v databázi.")
                    return

                # Vytvořit server
                server = Server(
                    name=server_name,
                    owner_id=user.id,
                    service_level=int(self.service_var.get()),
                    server_port=25565,
                    query_port=25565,
                    diagnostic_server_port=None,
                    build_version_id=build_version.id
                )
                db.session.add(server)
                db.session.commit()

                # Aktualizovat porty
                update_server_ports(server.id)
                
                messagebox.showinfo(
                    "Hotovo", 
                    f"Server '{server_name}' byl úspěšně vytvořen!\n\n"
                    f"Vlastník: {user.username}\n"
                    f"Build: {build_type.name} {build_version.mc_version}\n"
                    f"Úroveň služby: {server.service_level}"
                )
                self.root.destroy()
                
            except Exception as e:
                db.session.rollback()
                messagebox.showerror(
                    "Chyba", 
                    f"Nastala chyba při vytváření serveru:\n{str(e)}"
                )

    def update_versions(self, event=None):
        """Aktualizuje seznam verzí podle vybraného buildu"""
        selected_build = self.build_var.get()
        versions = self.builds.get(selected_build, [])
        self.version_dropdown['values'] = versions
        if versions:
            self.version_var.set(versions[0])

    def setup_ui(self):
        """Vytvoří GUI rozhraní"""
        # Styly
        style = ttk.Style()
        style.configure('TLabel', padding=5)
        style.configure('TButton', padding=5)
        style.configure('TCombobox', padding=5)
        style.configure('TEntry', padding=5)

        # Hlavní frame
        main_frame = ttk.Frame(self.root, padding=(15, 15))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Název serveru
        ttk.Label(main_frame, text="Název serveru:").grid(
            row=0, column=0, sticky="w", pady=(0, 5))
        self.entry_name = ttk.Entry(main_frame, width=30)
        self.entry_name.grid(row=0, column=1, pady=(0, 5), sticky="ew")
        self.entry_name.focus_set()

        # Vlastník serveru
        ttk.Label(main_frame, text="Vlastník serveru:").grid(
            row=1, column=0, sticky="w", pady=(0, 5))
        self.user_var = tk.StringVar()
        self.user_dropdown = ttk.Combobox(
            main_frame, 
            textvariable=self.user_var, 
            values=[f"{u.username} <{u.email}>" for u in self.users],
            state="readonly"
        )
        self.user_dropdown.grid(row=1, column=1, pady=(0, 5), sticky="ew")
        if self.users:
            self.user_var.set(f"{self.users[0].username} <{self.users[0].email}>")

        # Úroveň služby
        ttk.Label(main_frame, text="Úroveň služby:").grid(
            row=2, column=0, sticky="w", pady=(0, 5))
        self.service_var = tk.StringVar(value="1")
        self.service_dropdown = ttk.Combobox(
            main_frame,
            textvariable=self.service_var,
            values=["1", "2", "3"],
            state="readonly"
        )
        self.service_dropdown.grid(row=2, column=1, pady=(0, 5), sticky="ew")

        # Build
        ttk.Label(main_frame, text="Build:").grid(
            row=3, column=0, sticky="w", pady=(0, 5))
        self.build_var = tk.StringVar()
        self.build_dropdown = ttk.Combobox(
            main_frame,
            textvariable=self.build_var,
            values=list(self.builds.keys()),
            state="readonly"
        )
        self.build_dropdown.grid(row=3, column=1, pady=(0, 5), sticky="ew")

        # Verze
        ttk.Label(main_frame, text="Verze:").grid(
            row=4, column=0, sticky="w", pady=(0, 10))
        self.version_dropdown = ttk.Combobox(
            main_frame,
            textvariable=self.version_var,
            state="readonly"
        )
        self.version_dropdown.grid(row=4, column=1, pady=(0, 10), sticky="ew")

        # Nastavit výchozí build a verze
        if self.builds:
            self.build_var.set(next(iter(self.builds.keys())))
            self.update_versions()

        # Bind události
        self.build_dropdown.bind("<<ComboboxSelected>>", self.update_versions)

        # Tlačítko pro vytvoření
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(
            btn_frame,
            text="Vytvořit server",
            command=self.create_server,
            style='Accent.TButton' if 'Accent.TButton' in style.theme_names() else 'TButton'
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Zrušit",
            command=self.root.destroy
        ).pack(side=tk.LEFT, padx=5)

        # Nastavení gridu
        main_frame.columnconfigure(1, weight=1)
        
        # Bind Enter klávesy
        self.root.bind('<Return>', lambda e: self.create_server())

    def update_versions(self, event=None):
        """Aktualizuje seznam verzí podle vybraného buildu"""
        selected_build = self.build_var.get()
        versions = self.builds.get(selected_build, [])
        self.version_dropdown['values'] = versions
        if versions:
            self.version_var.set(versions[0])

if __name__ == "__main__":
    from app import app
    from models import db
    root = tk.Tk()
    app_gui = ServerCreatorApp(root, app)
    root.mainloop()