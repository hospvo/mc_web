# setup_admin.py
from app import app
from models import db, User

with app.app_context():
    admin = User.query.filter_by(email="hospvo@seznam.cz").first()
    if admin:
        admin.is_superadmin = True
        db.session.commit()
        print(f"✅ Superadmin nastaven pro {admin.username} (ID: {admin.id})")
    else:
        print("❌ Uživatel s tímto emailem neexistuje.")