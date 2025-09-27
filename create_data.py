import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple
import miniupnpc
import shutil
import subprocess
import time
import json
from pathlib import Path
from models import db, User, Server, BuildType, BuildVersion
from server_configs import update_server_ports
from mc_server import BASE_SERVERS_PATH, BASE_BUILD_PATH, get_server_status

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
        
        # Přidáme reference na tlačítka
        self.sync_button = None
        self.delete_button = None
        
        self.setup_ui()
        self.center_window()
        
        # Bind eventu pro změnu textu v entry
        self.entry_name.bind('<KeyRelease>', self.check_server_exists)
        
    def center_window(self):
        """Centruje okno na obrazovce"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')


    def check_server_exists(self, event=None):
        """Zkontroluje, zda server s daným názvem existuje v databázi a aktualizuje stav tlačítek"""
        server_name = self.entry_name.get().strip()
        
        if not server_name:
            # Pokud je pole prázdné, deaktivujeme tlačítka
            if self.sync_button:
                self.sync_button.config(state=tk.DISABLED)
            if self.delete_button:
                self.delete_button.config(state=tk.DISABLED)
            return
        
        with self.flask_app.app_context():
            server = Server.query.filter_by(name=server_name).first()
            server_exists = server is not None
            
            # Aktualizujeme stav tlačítek
            if self.sync_button:
                self.sync_button.config(state=tk.NORMAL if server_exists else tk.DISABLED)
            if self.delete_button:
                self.delete_button.config(state=tk.NORMAL if server_exists else tk.DISABLED)

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
        """Zkontroluje existenci složky serveru, vytvoří podsložky a připraví server jar"""
        folder_path = os.path.join(BASE_SERVERS_PATH, server_name)
        
        if os.path.exists(folder_path):
            return True

        result = messagebox.askyesno(
            "Složka neexistuje", 
            f"Složka pro server '{server_name}' neexistuje.\n\nCesta: {folder_path}\n\nChcete ji vytvořit?",
            icon='question'
        )

        selected_version = self.version_var.get()

        if "-" in selected_version:
            mc_version, build_number = selected_version.split("-", 1)
        else:
            mc_version, build_number = selected_version, None
        
        if result:
            try:
                # vytvoří složky
                os.makedirs(folder_path, exist_ok=True)
                mcbackups_path = os.path.join(folder_path, "mcbackups")
                minecraft_server_path = os.path.join(folder_path, "minecraft-server")
                os.makedirs(mcbackups_path, exist_ok=True)
                os.makedirs(minecraft_server_path, exist_ok=True)

                # Flask context pro DB dotazy
                with self.flask_app.app_context():
                    existing_server = Server.query.filter_by(name=server_name).first()
                    # získat budoucí server_id
                    if existing_server:
                        future_server_id = existing_server.id
                    else:
                        max_server = db.session.query(Server).order_by(Server.id.desc()).first()
                        future_server_id = (max_server.id + 1) if max_server else 1

                    # vybrat build a verzi podle GUI
                    build_type = BuildType.query.filter_by(name=self.build_var.get()).first()
                    build_version = BuildVersion.query.filter_by(
                        build_type=build_type,
                        mc_version=mc_version,
                        build_number=build_number
                    ).first()

                if build_version is None:
                    messagebox.showerror("Chyba", "Nepodařilo se najít vybraný build verze Minecraftu.")
                    return False

                version_folder = f"{mc_version}-{build_number}" if build_number else mc_version
                version_path = os.path.join(
                    BASE_BUILD_PATH,
                    build_type.name.upper(),
                    "versions",
                    version_folder
                )

                # SPECIÁLNÍ ZPRACOVÁNÍ PRO FORGE a FABRIC
                if build_type.name.upper() == "FORGE":
                    # Pro Forge kopírujeme všechny potřebné soubory
                    self.copy_forge_server_files(version_path, minecraft_server_path, future_server_id)

                elif build_type.name.upper() == "FABRIC":
                    # Pro Fabric kopírujeme jen bootstrap server.jar
                    jar_path = os.path.join(version_path, "server.jar")
                    if not os.path.exists(jar_path):
                        messagebox.showerror("Chyba", f"Fabric bootstrap server.jar nebyl nalezen: {version_path}")
                        return False

                    target_jar = os.path.join(minecraft_server_path, f"server_{future_server_id}.jar")
                    shutil.copy2(jar_path, target_jar)

                    print(f"[INFO] Fabric bootstrap zkopírován do {target_jar}")

                else:
                    # Původní logika pro ostatní buildy (Paper, Vanilla...)
                    jar_files = [f for f in os.listdir(version_path) if f.endswith(".jar")]
                    if not jar_files:
                        messagebox.showerror("Chyba", f"V této složce není žádný .jar soubor: {version_path}")
                        return False

                    source_jar = os.path.join(version_path, jar_files[0])
                    if not os.path.exists(source_jar):
                        messagebox.showerror("Chyba", f"Nepodařilo se najít soubor: {source_jar}")
                        return False

                    target_jar = os.path.join(minecraft_server_path, f"server_{future_server_id}.jar")
                    shutil.copy2(source_jar, target_jar)

                # Vytvořit start.bat soubor
                self.create_start_bat(minecraft_server_path, future_server_id, build_type.name)

                return True

            except Exception as e:
                messagebox.showerror(
                    "Chyba", 
                    f"Nepodařilo se vytvořit složky nebo zkopírovat soubory:\n{str(e)}"
                )
                return False
            
    def copy_forge_server_files(self, source_path: str, target_path: str, server_id: int):
        """Kopíruje všechny potřebné soubory pro Forge server"""
        try:
            # Kopírovat všechny soubory a složky kromě installer.jar
            for item in os.listdir(source_path):
                item_path = os.path.join(source_path, item)
                
                # Přeskočit instalátor
                if item == "installer.jar":
                    continue
                    
                target_item_path = os.path.join(target_path, item)
                
                if os.path.isfile(item_path):
                    shutil.copy2(item_path, target_item_path)
                elif os.path.isdir(item_path):
                    shutil.copytree(item_path, target_item_path, dirs_exist_ok=True)
            
            # Najít hlavní server jar soubor (může být pojmenován různě)
            jar_files = [f for f in os.listdir(target_path) 
                        if f.endswith(".jar") and not f.startswith("installer")]
            
            if jar_files:
                # Přejmenovat první nalezený jar na standardní název
                original_jar = os.path.join(target_path, jar_files[0])
                target_jar = os.path.join(target_path, f"server_{server_id}.jar")
                
                if original_jar != target_jar:
                    shutil.move(original_jar, target_jar)
            
            print(f"[INFO] Forge server files copied from {source_path} to {target_path}")
            
        except Exception as e:
            raise Exception(f"Chyba při kopírování Forge souborů: {str(e)}")

    def create_start_bat(self, server_path: str, server_id: int, build_type: str):
        """Vytvoří startovací batch soubor pro server"""
        jar_filename = f"server_{server_id}.jar"
        
        # SPECIÁLNÍ NASTAVENÍ PRO FORGE
        if build_type.upper() == "FORGE":
            bat_content = f"""@echo off
    title Minecraft Forge Server {server_id}
    echo Starting Minecraft Forge Server {server_id}...

    set JAVA_HOME=java
    set MAX_RAM=4G
    set MIN_RAM=2G

    java -Xmx%MAX_RAM% -Xms%MIN_RAM% -jar "{jar_filename}" nogui

    pause
    """
        else:
            # Původní nastavení pro ostatní buildy
            bat_content = f"""@echo off
    title Minecraft Server {server_id}
    echo Starting Minecraft Server {server_id}...

    set JAVA_HOME=java
    set MAX_RAM=2G
    set MIN_RAM=1G

    java -Xmx%MAX_RAM% -Xms%MIN_RAM% -jar "{jar_filename}" nogui

    pause
    """
        
        bat_path = os.path.join(server_path, "start.bat")
        with open(bat_path, 'w', encoding='utf-8') as bat_file:
            bat_file.write(bat_content)

    def configure_server_properties(self, server_path: str, server_port: int, query_port: int):
        """Konfiguruje server.properties soubor s příslušnými porty"""
        properties_path = os.path.join(server_path, "server.properties")
        
        # Pokud soubor neexistuje, vytvoříme výchozí
        if not os.path.exists(properties_path):
            default_properties = f"""#Minecraft server properties
#Generated by Minecraft Server Manager
server-port={server_port}
query.port={query_port}
enable-query=true
max-players=20
online-mode=false
motd=Minecraft Server Manager
spawn-protection=0
"""
            with open(properties_path, 'w', encoding='utf-8') as prop_file:
                prop_file.write(default_properties)
        else:
            # Pokud soubor existuje, aktualizujeme porty
            with open(properties_path, 'r', encoding='utf-8') as prop_file:
                lines = prop_file.readlines()
            
            # Aktualizace portů
            updated_lines = []
            for line in lines:
                if line.startswith('server-port='):
                    updated_lines.append(f'server-port={server_port}\n')
                elif line.startswith('query.port='):
                    updated_lines.append(f'query.port={query_port}\n')
                else:
                    updated_lines.append(line)
            
            with open(properties_path, 'w', encoding='utf-8') as prop_file:
                prop_file.writelines(updated_lines)

    def accept_eula(self, server_path: str):
        """Přijme EULA změnou eula.txt na true"""
        eula_path = os.path.join(server_path, "eula.txt")
        
        if os.path.exists(eula_path):
            with open(eula_path, 'r', encoding='utf-8') as eula_file:
                content = eula_file.read()
            
            # Nahradit false za true
            content = content.replace('eula=false', 'eula=true')
            
            with open(eula_path, 'w', encoding='utf-8') as eula_file:
                eula_file.write(content)
        else:
            # Vytvořit nový eula.txt soubor
            with open(eula_path, 'w', encoding='utf-8') as eula_file:
                eula_file.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://account.mojang.com/documents/minecraft_eula).\n")
                eula_file.write(f"#{time.strftime('%a %b %d %H:%M:%S %Z %Y')}\n")
                eula_file.write("eula=true\n")

    def start_and_verify_server(self, server_path: str, jar_path: str, max_wait: int = 60) -> Tuple[bool, str]:
        """Spustí server, ověří jeho běh a poté jej vypne. Vrací tuple (success, message)."""
        process = None
        log_file = os.path.join(server_path, "logs", "latest.log")
        debug_info = ""
        
        try:
            # Zajistíme existenci log složky
            log_dir = os.path.join(server_path, "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # Spustit server proces
            process = subprocess.Popen(
                ['java', '-Xmx1G', '-Xms512M', '-jar', os.path.basename(jar_path), 'nogui'],
                cwd=server_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Počkat na inicializaci
            server_started = False
            error_detected = False
            error_message = ""
            
            for i in range(max_wait):
                time.sleep(1)
                
                # Kontrola, zda proces ještě běží
                if process.poll() is not None:
                    # Proces skončil předčasně - pravděpodobně chyba
                    stdout, stderr = process.communicate()
                    error_detected = True
                    error_message = f"Server proces skončil s kódem {process.returncode}. "
                    if stdout:
                        error_message += f"STDOUT: {stdout[-500:]}"  # Posledních 500 znaků
                    if stderr:
                        error_message += f"STDERR: {stderr[-500:]}"
                    break
                
                # Kontrola log souboru pro úspěšné spuštění
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            log_content = f.read()
                            
                        if "Done" in log_content or "For help, type" in log_content:
                            server_started = True
                            debug_info = "Server úspěšně startoval (nalezen 'Done' v logu)"
                            break
                        elif "ERROR" in log_content or "Exception" in log_content:
                            error_detected = True
                            error_message = f"V logu nalezena chyba: {log_content[-500:]}"
                            break
                    except Exception as e:
                        debug_info = f"Chyba při čtení logu: {str(e)}"
                
                # Kontrola výstupu procesu
                try:
                    output = process.stdout.readline() if process.stdout else ""
                    if "Done" in output or "For help, type" in output:
                        server_started = True
                        debug_info = "Server úspěšně startoval (nalezen 'Done' ve výstupu)"
                        break
                    if "ERROR" in output or "Exception" in output:
                        error_detected = True
                        error_message = f"Ve výstupu nalezena chyba: {output}"
                        break
                except:
                    pass
            
            if error_detected:
                return False, f"Chyba při startu serveru: {error_message}"
            
            if not server_started:
                return False, f"Server se nespustil v časovém limitu {max_wait}s. {debug_info}"
            
            # Server běží, nyní jej bezpečně vypneme
            try:
                process.stdin.write("stop\n")
                process.stdin.flush()
            except:
                try:
                    process.terminate()
                except:
                    pass
            
            # Počkat na ukončení
            try:
                process.wait(timeout=15)
                return True, "Server úspěšně startován a vypnut"
            except subprocess.TimeoutExpired:
                process.kill()
                return False, "Server se nepodařilo řádně vypnout - byl násilně ukončen"
                
        except Exception as e:
            error_msg = f"Výjimka při spouštění serveru: {str(e)}"
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            return False, error_msg

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
        
        selected_version = self.version_var.get()
        if "-" in selected_version:
            mc_version, build_number = selected_version.split("-", 1)
        else:
            mc_version, build_number = selected_version, None

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
                    mc_version=mc_version,
                    build_number=build_number
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
                db.session.refresh(server)  # z DB načti nové porty

                # Cesta k serveru
                server_path = os.path.join(BASE_SERVERS_PATH, server_name, "minecraft-server")
                jar_path = os.path.join(server_path, f"server_{server.id}.jar")

                # Konfigurovat server.properties
                self.configure_server_properties(server_path, server.server_port, server.query_port)

                # Přijmout EULA
                self.accept_eula(server_path)

                # Ověřit server spuštěním a vypnutím
                verification_result, verification_msg = self.start_and_verify_server(server_path, jar_path)
                
                if not verification_result:
                    # Uložit informace o neúspěchu do databáze
                    server.status = "ERROR"
                    db.session.commit()
                    
                    # Nabídnout možnost otevření portů navzdory chybě
                    user_choice = messagebox.askyesno(
                        "Varování - Ověření serveru selhalo", 
                        f"Server '{server_name}' byl vytvořen, ale nepodařilo se ověřit jeho funkčnost.\n\n"
                        f"Chyba: {verification_msg}\n\n"
                        f"Zkontrolujte konfiguraci manuálně. Server je nyní nastaven na portech: "
                        f"{server.server_port} (server), {server.query_port} (query)\n\n"
                        f"⚠️  Porty se automaticky neotevřely z důvodu chyby ověření.\n"
                        f"Chcete je přesto otevřít přes UPnP?\n\n"
                        f"VAROVÁNÍ: Toto může být rizikové, pokud server nefunguje správně!",
                        icon='warning'
                    )
                    
                    if user_choice:
                        # Uživatel chce otevřít porty
                        upnp_success = self.open_upnp_ports(server.server_port, server.query_port)
                        if upnp_success:
                            messagebox.showinfo(
                                "Porty otevřeny", 
                                f"Porty {server.server_port} (server) a {server.query_port} (query) byly úspěšně otevřeny přes UPnP.\n\n"
                                f"Server zůstává v chybovém stavu - doporučujeme manuální kontrolu!"
                            )
                        else:
                            messagebox.showerror(
                                "Chyba UPnP", 
                                "Nepodařilo se otevřít porty přes UPnP.\n"
                                "Zkontrolujte nastavení routeru nebo otevřete porty manuálně."
                            )
                else:
                    # Úspěšné ověření - standardní otevření portů
                    upnp_success = self.open_upnp_ports(server.server_port, server.query_port)
                    upnp_status = f"Porty {server.server_port}, {server.query_port} otevřeny přes UPnP" if upnp_success else "Porty se nepodařilo otevřít přes UPnP"
                    
                    if upnp_success:
                        print(f"[INFO] {upnp_status}")
                    else:
                        print(f"[WARN] {upnp_status}")
                    
                    # Nastavit status serveru na úspěch
                    server.status = "READY"
                    db.session.commit()
                    
                    messagebox.showinfo(
                        "Hotovo", 
                        f"Server '{server_name}' byl úspěšně vytvořen a ověřen!\n\n"
                        f"Vlastník: {user.username}\n"
                        f"Build: {build_type.name} {build_version.mc_version}\n"
                        f"Úroveň služby: {server.service_level}\n"
                        f"Porty: {server.server_port} (server), {server.query_port} (query)\n"
                        f"{upnp_status}"
                    )
                
                self.root.destroy()
                
            except Exception as e:
                db.session.rollback()
                messagebox.showerror(
                    "Chyba", 
                    f"Nastala chyba při vytváření serveru:\n{str(e)}"
                )

    def delete_server(self):
        """Kompletně smaže server včetně složek a záznamů z databáze"""
        server_name = self.entry_name.get().strip()
        if not server_name:
            messagebox.showerror("Chyba", "Nejprve zadejte název serveru.")
            return

        with self.flask_app.app_context():
            try:
                # Najít server v databázi
                server = Server.query.filter_by(name=server_name).first()
                if not server:
                    messagebox.showerror("Chyba", f"Server '{server_name}' nebyl nalezen v databázi.")
                    return

                # Kontrola, zda server běží
                server_status = get_server_status(server.id)
                if server_status['status'] == 'running':
                    messagebox.showerror(
                        "Chyba", 
                        f"Server '{server_name}' je momentálně spuštěn.\n\n"
                        f"Nejprve zastavte server před jeho smazáním."
                    )
                    return

                # Potvrzení smazání
                confirm = messagebox.askyesno(
                    "Potvrzení smazání",
                    f"Opravdu chcete KOMPLETNĚ smazat server '{server_name}'?\n\n"
                    f"Tato akce smaže:\n"
                    f"- Všechna data serveru ze složky\n"
                    f"- Všechny zálohy\n"
                    f"- Záznam z databáze\n\n"
                    f"Tato akce je NEVRATNÁ!",
                    icon='warning'
                )
                
                if not confirm:
                    return

                # Smazání složek serveru
                server_folder = os.path.join(BASE_SERVERS_PATH, server_name)
                if os.path.exists(server_folder):
                    try:
                        shutil.rmtree(server_folder)
                        print(f"[INFO] Složka serveru smazána: {server_folder}")
                    except Exception as e:
                        messagebox.showerror(
                            "Chyba", 
                            f"Nepodařilo se smazat složku serveru:\n{str(e)}\n\n"
                            f"Složka: {server_folder}"
                        )
                        return

                # Smazání záznamu z databáze
                db.session.delete(server)
                db.session.commit()

                messagebox.showinfo(
                    "Hotovo", 
                    f"Server '{server_name}' byl úspěšně kompletně smazán.\n\n"
                    f"- Složky serveru odstraněny\n"
                    f"- Záznam z databáze smazán"
                )
                
                # Vyčištění vstupního pole
                self.entry_name.delete(0, tk.END)
                
            except Exception as e:
                db.session.rollback()
                messagebox.showerror(
                    "Chyba", 
                    f"Nastala chyba při mazání serveru:\n{str(e)}"
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

        # Uložíme reference na tlačítka a nastavíme je jako disabled na začátku
        self.sync_button = ttk.Button(
            btn_frame,
            text="Sync porty (1 server)",
            command=self.sync_ports_for_server,
            state=tk.DISABLED  # Na začátku disabled
        )
        self.sync_button.pack(side=tk.LEFT, padx=5)
        
        # Nové tlačítko pro smazání serveru
        self.delete_button = ttk.Button(
            btn_frame,
            text="Smazat server",
            command=self.delete_server,
            style='Danger.TButton' if 'Danger.TButton' in style.theme_names() else 'TButton',
            state=tk.DISABLED  # Na začátku disabled
        )
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Zrušit",
            command=self.root.destroy
        ).pack(side=tk.LEFT, padx=5)

        # Nastavení gridu
        main_frame.columnconfigure(1, weight=1)
        
        # Bind Enter klávesy
        self.root.bind('<Return>', lambda e: self.create_server())

    def sync_ports_for_server(self):
        """Synchronizuje porty jen pro jeden server"""
        server_name = self.entry_name.get().strip()
        if not server_name:
            messagebox.showerror("Chyba", "Nejprve zadejte název serveru.")
            return

        with self.flask_app.app_context():
            server = Server.query.filter_by(name=server_name).first()
            if not server:
                messagebox.showerror("Chyba", f"Server '{server_name}' nebyl nalezen v databázi.")
                return

            old_ports = (server.server_port, server.query_port)

            try:
                update_server_ports(server.id)

                db.session.refresh(server)  # Načteme nové hodnoty z DB
                new_ports = (server.server_port, server.query_port)

                # Aktualizovat server.properties
                server_path = os.path.join(BASE_SERVERS_PATH, server_name, "minecraft-server")
                self.configure_server_properties(server_path, server.server_port, server.query_port)

                messagebox.showinfo(
                    "Hotovo",
                    f"Porty byly aktualizovány pro server '{server_name}'.\n\n"
                    f"Staré porty: {old_ports}\n"
                    f"Nové porty: {new_ports}\n"
                    f"Soubor server.properties byl aktualizován."
                )
            except Exception as e:
                messagebox.showerror("Chyba", f"Nastala chyba při synchronizaci portů:\n{str(e)}")

    def open_upnp_ports(self, server_port: int, query_port: int = None) -> bool:
        """
        Pokusí se automaticky otevřít porty přes UPnP.
        Vrací True pokud se povedlo, jinak False.
        """
        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            ndevices = upnp.discover()
            if ndevices == 0:
                print("[UPnP] Router nebyl nalezen.")
                return False

            upnp.selectigd()
            external_ip = upnp.externalipaddress()
            print(f"[UPnP] Nalezen router, externí IP: {external_ip}")

            # otevření hlavního server portu (TCP i UDP)
            upnp.addportmapping(server_port, 'TCP', upnp.lanaddr, server_port, 'Minecraft Server TCP', '')
            upnp.addportmapping(server_port, 'UDP', upnp.lanaddr, server_port, 'Minecraft Server UDP', '')
            print(f"[UPnP] Otevřen port {server_port} (TCP/UDP).")

            # pokud máš query port, otevři i ten
            if query_port and query_port != server_port:
                upnp.addportmapping(query_port, 'UDP', upnp.lanaddr, query_port, 'Minecraft Query UDP', '')
                print(f"[UPnP] Otevřen query port {query_port} (UDP).")

            return True

        except Exception as e:
            print(f"[UPnP] Nepodařilo se otevřít porty: {e}")
            return False


if __name__ == "__main__":
    from app import app
    from models import db
    root = tk.Tk()
    app_gui = ServerCreatorApp(root, app)
    root.mainloop()