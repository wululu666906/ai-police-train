import models
from database import SessionLocal, engine

def init_db():
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add_all(
                [
                    models.User(username="admin", hashed_password="123456", role="admin"),
                    models.User(username="student001", hashed_password="123456", role="student"),
                ]
            )
            db.commit()
    finally:
        db.close()
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
