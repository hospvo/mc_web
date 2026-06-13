# port_manager.py
import subprocess
import sys
import miniupnpc
from typing import Tuple, Optional

def open_upnp_ports(server_port: int, query_port: Optional[int] = None) -> bool:
    """Otevře porty přes UPnP. Vrací True při úspěchu alespoň jednoho portu."""
    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        if upnp.discover() == 0:
            print("[UPnP] Router nebyl nalezen.")
            return False

        upnp.selectigd()
        lan_addr = upnp.lanaddr
        success = False

        # Hlavní server port (TCP + UDP)
        for proto in ['TCP', 'UDP']:
            try:
                upnp.addportmapping(server_port, proto, lan_addr, server_port, f'Minecraft Server {proto}', '')
                print(f"[UPnP] Otevřen port {server_port}/{proto}")
                success = True
            except Exception as e:
                print(f"[UPnP] Chyba při otevírání {server_port}/{proto}: {e}")

        # Query port (pouze UDP, pokud je jiný než server_port)
        if query_port and query_port != server_port:
            try:
                upnp.addportmapping(query_port, 'UDP', lan_addr, query_port, 'Minecraft Query', '')
                print(f"[UPnP] Otevřen query port {query_port}/UDP")
                success = True
            except Exception as e:
                print(f"[UPnP] Chyba při otevírání query portu {query_port}: {e}")

        return success
    except Exception as e:
        print(f"[UPnP] Obecná chyba: {e}")
        return False

def close_upnp_ports(server_port: int, query_port: Optional[int] = None) -> bool:
    """Zavře porty přes UPnP."""
    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        if upnp.discover() == 0:
            return False
        upnp.selectigd()
        success = False

        for proto in ['TCP', 'UDP']:
            try:
                upnp.deleteportmapping(server_port, proto)
                print(f"[UPnP] Zavřen port {server_port}/{proto}")
                success = True
            except:
                pass

        if query_port and query_port != server_port:
            try:
                upnp.deleteportmapping(query_port, 'UDP')
                print(f"[UPnP] Zavřen query port {query_port}/UDP")
                success = True
            except:
                pass
        return success
    except Exception as e:
        print(f"[UPnP] Chyba při zavírání: {e}")
        return False

def open_windows_firewall_ports(server_port: int, query_port: Optional[int] = None, server_id: int = None) -> bool:
    """Přidá pravidla do Windows Firewall (vyžaduje administrátorská práva)."""
    if sys.platform != 'win32':
        return False
    rule_name_base = f"Minecraft Server {server_id}" if server_id else "Minecraft Server"
    success = True
    # Hlavní port TCP
    cmd = f'netsh advfirewall firewall add rule name="{rule_name_base} TCP" dir=in action=allow protocol=TCP localport={server_port}'
    if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
        success = False
    # Hlavní port UDP
    cmd = f'netsh advfirewall firewall add rule name="{rule_name_base} UDP" dir=in action=allow protocol=UDP localport={server_port}'
    if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
        success = False
    # Query port (UDP)
    if query_port and query_port != server_port:
        cmd = f'netsh advfirewall firewall add rule name="{rule_name_base} Query" dir=in action=allow protocol=UDP localport={query_port}'
        if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
            success = False
    return success

def close_windows_firewall_ports(server_port: int, query_port: Optional[int] = None, server_id: int = None) -> bool:
    """Odstraní pravidla Windows Firewall."""
    if sys.platform != 'win32':
        return False
    rule_name_base = f"Minecraft Server {server_id}" if server_id else "Minecraft Server"
    success = True
    for name_suffix in ["TCP", "UDP", "Query"]:
        full_name = f"{rule_name_base} {name_suffix}".strip()
        cmd = f'netsh advfirewall firewall delete rule name="{full_name}"'
        if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
            # Neúspěch neřešíme, pravidlo možná neexistuje
            pass
    return success

def ensure_ports_open(server_id: int, server_port: int, query_port: Optional[int] = None) -> Tuple[bool, bool]:
    """
    Zajistí otevření portů (UPnP + lokální firewall).
    Vrací (upnp_success, firewall_success).
    """
    upnp_ok = open_upnp_ports(server_port, query_port)
    fw_ok = open_windows_firewall_ports(server_port, query_port, server_id)
    return upnp_ok, fw_ok

def ensure_ports_closed(server_id: int, server_port: int, query_port: Optional[int] = None) -> None:
    """Zavře porty (volitelné)."""
    close_upnp_ports(server_port, query_port)
    close_windows_firewall_ports(server_port, query_port, server_id)