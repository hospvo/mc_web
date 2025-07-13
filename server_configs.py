import os
import yaml
from app import app
from models import db, Server
from mc_server import get_server_paths
from sqlalchemy import select

def update_plugin_config(server_id):
    with app.app_context():
        try:
            server = db.session.execute(
                select(Server).where(Server.id == server_id)
            ).scalar_one_or_none()
            
            if not server:
                print(f"Server with ID {server_id} not found")
                return False
            
            if not isinstance(server.name, str) or not server.name.strip():
                print(f"Invalid server name for ID {server_id}")
                return False
            
            paths = get_server_paths(server_id)
            if not paths or 'server_path' not in paths:
                print("Invalid server paths configuration")
                return False
            
            config_path = os.path.join(paths['server_path'], "plugins", "PlayerStatusPlugin", "config.yml")
            
            # Načtení nebo vytvoření konfigurace
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Vždy nastavíme unikátní port
            unique_port = 8080 + server_id
            config['port'] = unique_port
            config['server_name'] = server.name

            # Zápis do databáze (diagnostický port)
            server.diagnostic_server_port = unique_port
            db.session.commit()
            
            # Atomický zápis konfigurace
            temp_path = f"{config_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False)
            os.replace(temp_path, config_path)
            
            print(f"Updated config and database for server {server_id} (port: {unique_port})")
            return True
            
        except Exception as e:
            print(f"Error processing server {server_id}: {e}")
            db.session.rollback()
            return False

def update_server_ports(server_id):
    with app.app_context():
        try:
            # 1. Načtení serveru z DB
            server = Server.query.get(server_id)
            if not server:
                print(f"Server s ID {server_id} nebyl nalezen")
                return False

            # 2. Získání všech používaných portů
            used_ports = set()
            for s in Server.query.all():
                if s.id != server_id:  # Ignorujeme aktuální server
                    used_ports.add(s.server_port)
                    if s.query_port:  # Pokud je query_port nastaven
                        used_ports.add(s.query_port)

            # 3. Najít volné porty (s garantovaným rozestupem)
            def find_available_port_pair(start_port=25565):
                port = start_port
                while True:
                    # Hlavní port musí být sudý, query port následující liché číslo
                    if (port % 2 == 0 and 
                        port not in used_ports and 
                        (port + 1) not in used_ports):
                        return port, port + 1
                    port += 1
                    if port > 30000:  # Bezpečný limit
                        raise ValueError("Nebyl nalezen žádný volný port")

            minecraft_port, query_port = find_available_port_pair()

            # 4. Aktualizace server.properties
            paths = get_server_paths(server_id)
            if not paths or 'server_path' not in paths:
                print("Neplatná konfigurace cest k serveru")
                return False

            server_properties_path = os.path.join(paths['server_path'], 'server.properties')
            
            if os.path.exists(server_properties_path):
                with open(server_properties_path, 'r+', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Regex pro nahrazení portů a povolení query
                    import re
                    content = re.sub(r'server-port=\d+', f'server-port={minecraft_port}', content)
                    content = re.sub(r'query\.port=\d+', f'query.port={query_port}', content)
                    
                    # Povolení query protokolu
                    content = re.sub(r'enable-query=(true|false)', 'enable-query=true', content)
                    
                    # Pokud položky neexistovaly, přidáme je
                    if 'server-port=' not in content:
                        content += f'\nserver-port={minecraft_port}'
                    if 'query.port=' not in content:
                        content += f'\nquery.port={query_port}'
                    if 'enable-query=' not in content:
                        content += '\nenable-query=true'
                    
                    f.seek(0)
                    f.write(content)
                    f.truncate()
            else:
                # Pokud soubor neexistuje, vytvoříme základní konfiguraci
                with open(server_properties_path, 'w', encoding='utf-8') as f:
                    content = f"""# Minecraft server properties
                    server-port={minecraft_port}
                    query.port={query_port}
                    enable-query=true
                    """
                    f.write(content)

            # 5. Aktualizace databáze
            server.server_port = minecraft_port
            server.query_port = query_port
            db.session.commit()

            print(f"Aktualizovány porty pro server {server_id}: "
                  f"hlavní={minecraft_port}, query={query_port}")
            return True

        except Exception as e:
            print(f"Chyba při aktualizaci portů pro server {server_id}: {e}")
            db.session.rollback()
            return False


if __name__ == '__main__':
    all_server = [1, 2, 3]  # ID serverů
    
    with app.app_context():
        if not os.path.exists('instance/db.sqlite3'):
            db.create_all()
        
        for server_id in all_server:
            #update_plugin_config(server_id)
            update_server_ports(server_id)