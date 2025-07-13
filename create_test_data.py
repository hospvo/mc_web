from app import app
from models import db, User, Server

with app.app_context():
    user = User.query.get(1)
    if user:
        server = Server(name='Test', owner_id=user.id, service_level=3)
        db.session.add(server)
        db.session.commit()
        print("Test server byl vytvořen.")
    else:
        print("Uživatel s ID 1 neexistuje.")
