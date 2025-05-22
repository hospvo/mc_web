from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# Spojovací tabulka pro M:N vztah mezi servery a adminy
server_admins = db.Table('server_admins',
    db.Column('server_id', db.Integer, db.ForeignKey('server.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
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
    admin_of_servers = db.relationship('Server', secondary=server_admins, backref='admins', lazy='dynamic')

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

    def __repr__(self):
        return f'<Server {self.name}, Owner {self.owner.username}>'