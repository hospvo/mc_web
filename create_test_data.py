from app import app
from models import db, User, Server

with app.app_context():
    user = User.query.get(1)
    if user:
        server = Server(name='test_1', owner_id=user.id, service_level=1)
        db.session.add(server)
        db.session.commit()
        print("Test server byl vytvořen.")
    else:
        print("Uživatel s ID 1 neexistuje.")
