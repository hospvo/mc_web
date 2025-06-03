from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

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