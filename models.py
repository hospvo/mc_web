from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

# Spojovací tabulka pro M:N vztah mezi servery a adminy
server_admins = db.Table('server_admins',
    db.Column('server_id', db.Integer, db.ForeignKey('server.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# Spojovací tabulka pro M:N vztah mezi servery a pluginy
server_plugins = db.Table('server_plugins',
    db.Column('server_id', db.Integer, db.ForeignKey('server.id'), primary_key=True),
    db.Column('plugin_id', db.Integer, db.ForeignKey('plugin.id'), primary_key=True),
    db.Column('installed_at', db.DateTime, default=datetime.utcnow),
    db.Column('is_active', db.Boolean, default=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_active_db = db.Column(db.Boolean, default=True)
    # Servery, které uživatel vlastní (jeden vlastník → více serverů)
    owned_servers = db.relationship('Server', backref='owner', lazy=True)
    # Servery, na kterých je uživatel adminem (M:N vztah)
    admin_of_servers = db.relationship('Server', secondary=server_admins, 
                                     backref='admins', lazy='dynamic')

    @property
    def is_active(self):
        return self.is_active_db

    def __repr__(self):
        return f'<User {self.username}>'

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Vlastník serveru
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Úroveň služby (1 = základní, 2 = pokročilá, 3 = prémiová)
    service_level = db.Column(db.Integer, nullable=False)
    # Nové pole pro port serveru (defaultně 25565 - hlavní Minecraft port)
    server_port = db.Column(db.Integer, nullable=False, default=25565)
    # Query port 
    query_port = db.Column(db.Integer, nullable=False, default=25565)
    # Pole pro servisní port přes které vrací API
    diagnostic_server_port = db.Column(db.Integer, nullable=True)
    # informace o buildu  
    build_version_id = db.Column(db.Integer, db.ForeignKey('build_version.id'), nullable=False)
    # Nainstalované pluginy (M:N vztah)
    plugins = db.relationship('Plugin', secondary=server_plugins, 
                            backref='servers', lazy='dynamic')


    def __repr__(self):
        return f'<Server {self.name}, Owner {self.owner.username}>'

class Plugin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100))
    description = db.Column(db.Text)
    version = db.Column(db.String(50))
    author = db.Column(db.String(100))
    # Cesta k souboru na externím úložišti
    file_path = db.Column(db.String(255), nullable=False)
    # URL pro aktualizace
    download_url = db.Column(db.String(255))
    # Typ pluginů (core/optional/deprecated)
    plugin_type = db.Column(db.String(50), default='optional')
    # Kompatibilita (Folia verze)
    compatible_with = db.Column(db.String(100))
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    # Kategorie pro organizaci
    category = db.Column(db.String(50))
    #zdroj stažení
    source  =db.Column(db.String(50))
    # Závislosti (JSON seznam názvů pluginů)
    dependencies = db.Column(db.Text)

    def __repr__(self):
        return f'<Plugin {self.name} v{self.version}>'

class PluginConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugin.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    # Konfigurace v JSON formátu
    config_data = db.Column(db.Text)
    # Cesta k souboru konfigurace na serveru
    config_path = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    plugin = db.relationship('Plugin', backref='configurations')
    server = db.relationship('Server', backref='plugin_configs')

    def __repr__(self):
        return f'<Config for {self.plugin.name} on {self.server.name}>'

class PluginUpdateLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugin.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50))  # install/update/uninstall
    version_from = db.Column(db.String(50))
    version_to = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    plugin = db.relationship('Plugin', backref='update_logs')
    user = db.relationship('User', backref='plugin_actions')

    def __repr__(self):
        return f'<UpdateLog {self.action} {self.plugin.name} by {self.user.username}>'
    
class BuildType(db.Model):
    __tablename__ = 'build_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # např. 'Paper', 'Purpur'
    description = db.Column(db.Text)

    versions = db.relationship('BuildVersion', backref='build_type', lazy=True)

    def __repr__(self):
        return f'<BuildType {self.name}>'

class BuildVersion(db.Model):
    __tablename__ = 'build_version'
    id = db.Column(db.Integer, primary_key=True)
    build_type_id = db.Column(db.Integer, db.ForeignKey('build_type.id'), nullable=False)
    mc_version = db.Column(db.String(20), nullable=False)   # např. '1.20.1'
    build_number = db.Column(db.String(50))                 # např. '47.3.0' (Forge) nebo '152' (Paper)
    download_url = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    servers = db.relationship('Server', backref='build_version', lazy=True)

    def __repr__(self):
        return f'<BuildVersion {self.build_type.name} {self.mc_version}>'
    
class Mod(db.Model):
    __tablename__ = "mod"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)              # slug nebo unikátní identifikátor
    display_name = db.Column(db.String(100))                      # čitelný název
    description = db.Column(db.Text)
    version = db.Column(db.String(50))
    author = db.Column(db.String(100))
    file_path = db.Column(db.String(255), nullable=False)         # cesta k .jar souboru
    download_url = db.Column(db.String(500))
    source = db.Column(db.String(50), default="modrinth")         # modrinth / curseforge / manuál
    plugin_type = db.Column(db.String(50), default="optional")    # core/optional/deprecated
    category = db.Column(db.String(50))                           # např. "tech", "magic"
    compatible_with = db.Column(db.String(100))                   # seznam verzí MC/Forge
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # vztah k serverům (M:N)
    servers = db.relationship("Server", secondary="server_mods", backref="mods", lazy="dynamic")

    def __repr__(self):
        return f"<Mod {self.name} v{self.version}>"

# M:N spojovací tabulka mezi servery a módy
server_mods = db.Table(
    "server_mods",
    db.Column("server_id", db.Integer, db.ForeignKey("server.id"), primary_key=True),
    db.Column("mod_id", db.Integer, db.ForeignKey("mod.id"), primary_key=True),
    db.Column("installed_at", db.DateTime, default=datetime.utcnow),
    db.Column("is_active", db.Boolean, default=True),
)

class ModConfig(db.Model):
    __tablename__ = "mod_config"

    id = db.Column(db.Integer, primary_key=True)
    mod_id = db.Column(db.Integer, db.ForeignKey("mod.id"), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey("server.id"), nullable=False)
    config_path = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    mod = db.relationship("Mod", backref="configurations")
    server = db.relationship("Server", backref="mod_configs")

class ModUpdateLog(db.Model):
    __tablename__ = "mod_update_log"

    id = db.Column(db.Integer, primary_key=True)
    mod_id = db.Column(db.Integer, db.ForeignKey("mod.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(50))  # install/update/uninstall
    version_from = db.Column(db.String(50))
    version_to = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    mod = db.relationship("Mod", backref="update_logs")
    user = db.relationship("User", backref="mod_actions")
