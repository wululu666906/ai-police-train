import models
import os
from database import SessionLocal, engine
from routers.auth import hash_password

def init_db():
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            username = os.getenv("INITIAL_ADMIN_USERNAME", "").strip()
            password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
            if username and len(password) >= 12:
                db.add(models.User(username=username, hashed_password=hash_password(password), role="admin"))
                print(f"Created initial administrator: {username}")
            else:
                print(
                    "No administrator was created. Set INITIAL_ADMIN_USERNAME and "
                    "INITIAL_ADMIN_PASSWORD (at least 12 characters) before initializing an empty database."
                )
            db.commit()
    finally:
        db.close()
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
