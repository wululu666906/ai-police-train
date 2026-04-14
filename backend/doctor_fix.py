import database, models
from sqlalchemy.orm import Session

def fix_system():
    db = next(database.get_db())
    
    # 1. 检查并创建 Admin 用户
    admin = db.query(models.User).filter(models.User.username == 'admin').first()
    if not admin:
        print("Creating admin user...")
        new_admin = models.User(
            username='admin',
            hashed_password='123456', # MVP 方案
            role='admin'
        )
        db.add(new_admin)
        db.commit()
    else:
        print("Admin user already exists.")

    # 2. 检查并创建示例案件
    case_count = db.query(models.Case).count()
    if case_count == 0:
        print("Seeding sample case...")
        new_case = models.Case(
            title="东二环路口打架纠纷",
            case_type="治安警情",
            background="两名驾驶员因强行变道发生口角，随后升级为肢体冲突，交通大面积拥堵。"
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)
        
        new_scene = models.Scene(
            case_id=new_case.id,
            name="案发现场第一接触",
            difficulty="简单"
        )
        db.add(new_scene)
        db.commit()
        db.refresh(new_scene)
        
        new_role = models.Role(
            scene_id=new_scene.id,
            name="张三(路怒司机)",
            personality="急躁、认为自己受委屈、对警察不信任",
            init_emotion=80,
            init_trust=20,
            hidden_truths="['张三其实是无证驾驶','对方先骂的人','张三车内有管制刀具']"
        )
        db.add(new_role)
        db.commit()
        print("Sample data seeded.")
    else:
        print(f"Database already has {case_count} cases.")

if __name__ == "__main__":
    fix_system()
