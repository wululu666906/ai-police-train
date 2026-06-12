"""
Seed 20 pixel-art avatar images metadata into the database.
Run: python seed_avatars.py
"""
from database import SessionLocal, engine
from models import Base, AvatarImage

AVATARS = [
    # 年轻男性 (1-5)
    AvatarImage(filename="avatar_01.svg", gender="male", age_group="young"),
    AvatarImage(filename="avatar_02.svg", gender="male", age_group="young"),
    AvatarImage(filename="avatar_03.svg", gender="male", age_group="young"),
    AvatarImage(filename="avatar_04.svg", gender="male", age_group="young"),
    AvatarImage(filename="avatar_05.svg", gender="male", age_group="young"),
    # 年轻女性 (6-10)
    AvatarImage(filename="avatar_06.svg", gender="female", age_group="young"),
    AvatarImage(filename="avatar_07.svg", gender="female", age_group="young"),
    AvatarImage(filename="avatar_08.svg", gender="female", age_group="young"),
    AvatarImage(filename="avatar_09.svg", gender="female", age_group="young"),
    AvatarImage(filename="avatar_10.svg", gender="female", age_group="young"),
    # 中年男性 (11-15)
    AvatarImage(filename="avatar_11.svg", gender="male", age_group="middle"),
    AvatarImage(filename="avatar_12.svg", gender="male", age_group="middle"),
    AvatarImage(filename="avatar_13.svg", gender="male", age_group="middle"),
    AvatarImage(filename="avatar_14.svg", gender="male", age_group="middle"),
    AvatarImage(filename="avatar_15.svg", gender="male", age_group="middle"),
    # 中年女性 (16-20)
    AvatarImage(filename="avatar_16.svg", gender="female", age_group="middle"),
    AvatarImage(filename="avatar_17.svg", gender="female", age_group="middle"),
    AvatarImage(filename="avatar_18.svg", gender="female", age_group="middle"),
    AvatarImage(filename="avatar_19.svg", gender="female", age_group="middle"),
    AvatarImage(filename="avatar_20.svg", gender="female", age_group="middle"),
]


def seed_avatars():
    print("Creating avatar_images table...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(AvatarImage).count()
        if existing > 0:
            print(f"Avatars already seeded ({existing} records). Skipping.")
            return

        db.add_all(AVATARS)
        db.commit()
        print(f"Seeded {len(AVATARS)} avatar images.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_avatars()
