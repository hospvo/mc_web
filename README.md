# Minecraft Hosting Web

Webová aplikace pro správu Minecraft serverů. Projekt je postavený na Flasku a umožňuje uživatelům spravovat vlastní servery, pluginy, módy, modpacky, zálohy, konzoli serveru a hráčský přístup.

## Hlavní funkce

- registrace a přihlášení uživatelů
- dashboard s přehledem serverů
- start, stop a restart Minecraft serveru
- zobrazení stavu serveru, hráčů a konzolových logů
- správa záloh světů
- správa pluginů a módů
- vytváření a stahování modpacků
- hráčský přístup přes přístupové kódy
- administrační část pro servery, uživatele, buildy, módy a pluginy
- synchronizace dostupných buildů pro Paper, Folia, Fabric a Forge

## Požadavky

- Python 3.11 nebo novější
- Java pro spouštění Minecraft serverů
- Windows prostředí je aktuálně nejlépe podporované
- volitelné: administrátorská práva pro automatickou správu Windows Firewall pravidel

## Instalace

1. Naklonujte nebo otevřete projekt:

```powershell
cd C:\Users\hospv\Documents\GitHub\mc_web
```

2. Vytvořte virtuální prostředí:

```powershell
python -m venv venv
```

3. Aktivujte virtuální prostředí:

```powershell
.\venv\Scripts\Activate.ps1
```

4. Nainstalujte závislosti:

```powershell
pip install -r requirements.txt
```

## Konfigurace

Projekt používá soubor `.env`. Jako vzor slouží `.env.example`.

```powershell
Copy-Item .env.example .env
```

V `.env` nastavte hlavně:

```env
SECRET_KEY=change-me
DATABASE_URI=sqlite:///db.sqlite3

BASE_SERVERS_PATH=C:\Users\your-user\Documents\minecraft_server
BASE_PLUGIN_PATH=C:\Users\your-user\Documents\minecraft_plugins
BASE_BUILD_PATH=C:\Users\your-user\Documents\minecraft_builds
BASE_MODS_PATH=C:\Users\your-user\Documents\minecraft_mods

MINECRAFT_JAVA_PATH=java

PORT_RANGE_START=25566
PORT_RANGE_END=30000
```

Popis důležitých hodnot:

- `SECRET_KEY`: tajný klíč Flask aplikace. V produkci musí být unikátní a neveřejný.
- `DATABASE_URI`: cesta k databázi. Výchozí hodnota používá SQLite.
- `BASE_SERVERS_PATH`: složka, kde budou vytvořené Minecraft servery.
- `BASE_PLUGIN_PATH`: složka s uloženými pluginy.
- `BASE_BUILD_PATH`: složka se staženými server buildy.
- `BASE_MODS_PATH`: složka s módy a daty pro modpacky.
- `MINECRAFT_JAVA_PATH`: cesta k Java spustitelnému souboru.
- `PORT_RANGE_START` a `PORT_RANGE_END`: rozsah portů pro nové servery.

## Databáze

Projekt používá Flask-Migrate a SQLAlchemy.

Pro aplikování migrací spusťte:

```powershell
flask db upgrade
```

Při vývojovém spuštění přes `python app.py` se databáze vytvoří automaticky, pokud ještě neexistuje soubor `db.sqlite3`.

## Spuštění aplikace

Vývojové spuštění:

```powershell
python app.py
```

Aplikace poběží typicky na:

```text
http://127.0.0.1:5000
```

Pro produkční provoz nepoužívejte Flask debug server. V `requirements.txt` je dostupný `waitress`, takže lze aplikaci spustit například přes produkční WSGI server.

## Vytvoření admina

1. Nejprve si v aplikaci vytvořte běžný uživatelský účet.
2. Potom nastavte daného uživatele jako superadmina.

V projektu je pomocný skript `m_create_super_admin.py`, který aktuálně hledá konkrétní email. Před použitím upravte email ve skriptu:

```python
admin = User.query.filter_by(email="vas-email@example.com").first()
```

Potom spusťte:

```powershell
python m_create_super_admin.py
```

Admin rozhraní je dostupné na:

```text
/admin
```

## Synchronizace buildů

Projekt obsahuje skripty pro načtení dostupných buildů:

- `sync_paper.py`
- `sync_folia.py`
- `sync_fabric.py`
- `sync_forge.py`

Tyto skripty ukládají metadata do databáze a stahují server soubory do složky nastavené přes `BASE_BUILD_PATH`.

## Pomocné skripty mimo webovou aplikaci

Některé Python soubory v projektu nejsou nutnou součástí běžného běhu webové aplikace. Slouží jako jednorázové nástroje, vývojové utility, GUI správci nebo importovací skripty. Před spuštěním těchto skriptů je vhodné zkontrolovat jejich obsah, protože některé mohou mazat data, měnit databázi nebo upravovat soubory Minecraft serverů.

| Soubor | Typ | Účel |
| --- | --- | --- |
| `clean_dtbs.py` | údržba databáze | CLI nástroj pro mazání dat, mazání konkrétních tabulek, mazání modů nebo reset databáze. Používat opatrně. |
| `create_data.py` | Tkinter GUI | Starší/samostatný nástroj pro vytváření a správu serverů mimo webové rozhraní. |
| `create_test_data.py` | testovací helper | Vytvoří jednoduchý testovací server pro uživatele s ID `1`. |
| `import_plugins.py` | importovací skript | Stáhne předdefinovaný seznam pluginů a uloží je do databáze i souborového úložiště. |
| `m_create_super_admin.py` | administrační helper | Nastaví konkrétního uživatele podle emailu jako superadmina. Před použitím upravit email ve skriptu. |
| `manage.py` | Tkinter GUI | Integrovaný desktopový správce pro módy, pluginy, buildy, servery, statistiky a nástroje. |
| `manage_builds.py` | Tkinter GUI | Desktopový správce stažených buildů v databázi. |
| `manage_mods.py` | Tkinter GUI | Desktopový správce módů v databázi a na disku. |
| `manage_plugins.py` | Tkinter GUI | Desktopový správce pluginů v databázi a na disku. |
| `server_configs.py` | údržbový skript | Aktualizuje porty serverů a konfigurační soubory pro diagnostický/plugin port. Obsahuje pevně nastavená ID serverů. |
| `sync_paper.py` | synchronizace buildů | Načítá a ukládá dostupné Paper buildy. |
| `sync_folia.py` | synchronizace buildů | Načítá a ukládá dostupné Folia buildy. |
| `sync_fabric.py` | synchronizace buildů | Načítá a ukládá dostupné Fabric buildy. |
| `sync_forge.py` | synchronizace buildů | Načítá a ukládá dostupné Forge buildy. |
| `update_mod_client_server_side.py` | datový update | Doplní u modů v databázi hodnoty `client_side` a `server_side` z Modrinth API. |

Tyto soubory jsou naopak součástí hlavní webové aplikace nebo jejích backend helperů:

| Soubor | Role |
| --- | --- |
| `app.py` | hlavní Flask aplikace |
| `app_config.py` | konfigurace projektu |
| `auth.py` | přihlášení, registrace a odhlášení |
| `admin.py` | administrační webové rozhraní |
| `models.py` | databázové modely |
| `mc_server.py` | server API a runtime logika |
| `routes_mods.py` | API pro módy a modpacky |
| `routes_notices.py` | API pro oznámení |
| `player_view.py` | hráčský webový pohled |
| `server_creator.py` | helper pro vytváření serverů z webu |
| `plugin_instaler_modrinth.py` | helper pro získání pluginů z Modrinth |
| `port_manager.py` | helper pro UPnP a Windows Firewall |

## Struktura projektu

```text
mc_web/
|-- app.py                    # hlavní Flask aplikace
|-- app_config.py             # načítání konfigurace z .env
|-- auth.py                   # registrace, přihlášení a odhlášení
|-- admin.py                  # administrační rozhraní
|-- mc_server.py              # API a logika správy Minecraft serverů
|-- routes_mods.py            # API pro módy a modpacky
|-- routes_notices.py         # oznámení pro server
|-- player_view.py            # hráčský pohled na server
|-- models.py                 # databázové modely
|-- server_creator.py         # vytváření nových serverů
|-- port_manager.py           # správa portů a firewallu
|-- templates/                # HTML šablony
|-- static/                   # CSS, JavaScript a obrázky
|-- migrations/               # databázové migrace
`-- requirements.txt          # Python závislosti
```

## Statické soubory

CSS soubory jsou ve složce:

```text
static/css
```

JavaScript soubory jsou ve složce:

```text
static/js
```

Obrázky jsou ve složce:

```text
static/img
```

Pokud přidáváte audio soubory, doporučená složka je:

```text
static/audio
```

## Užitečné vývojové poznámky

- Většina uživatelských stránek dědí z `templates/base.html`.
- Admin stránky dědí z `templates/admin/base_admin.html`.
- Hlavní panel serveru je v `templates/includes/_server_panel.html`.
- Nové routy je vhodné přidávat do existujících blueprintů podle oblasti, které se týkají.
- U akcí nad serverem vždy ověřujte, že aktuální uživatel má k serveru přístup.
- Pro nové formuláře a API akce počítejte s kontrolou oprávnění a validací vstupů.

## Bezpečnostní poznámky

Před veřejným nasazením doporučeno zkontrolovat:

- vypnout debug režim
- nastavit silný `SECRET_KEY`
- nepoužívat výchozí hodnoty z `.env.example`
- přidat CSRF ochranu pro formuláře a stav měnící API požadavky
- ověřovat oprávnění u všech endpointů pracujících se `server_id`
- sanitizovat názvy souborů, záloh a logů
- nespouštět aplikaci pod účtem s vyššími právy, než je nutné
- nezveřejňovat `.env`, databázi ani složky se servery

## Licence

Licence zatím není určena. Pokud má být projekt veřejný, doplňte vhodný licenční soubor.
