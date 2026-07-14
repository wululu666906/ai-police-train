import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_ai_police.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

mock_chroma_client = MagicMock()
mock_chroma_collection = MagicMock()
mock_chroma_collection.count.return_value = 0
mock_chroma_collection.get.return_value = {"documents": []}
mock_chroma_collection.query.return_value = {"documents": [[]]}
mock_chroma_client.get_or_create_collection.return_value = mock_chroma_collection
mock_chroma_client.get_collection.return_value = mock_chroma_collection

patch("chromadb.PersistentClient", return_value=mock_chroma_client).start()

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from routers.auth import hash_password
from database import engine as _db_engine, SessionLocal, get_db

import models


def _remove_test_db():
    _db_engine.dispose()
    try:
        os.remove(TEST_DB_PATH)
    except FileNotFoundError:
        pass
    except PermissionError:
        pass


@pytest.fixture(autouse=True)
def mock_llm_provider():
    with patch("services.llm_provider.create_json_chat_completion") as mock:
        mock.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "response": "（测试模式：模拟角色回复）事情是这样的，我和对方确实有一些矛盾。",
                                "inner_thought": "测试模式内心活动：不想说太多。",
                                "updated_emotion": 55,
                                "updated_trust": 35,
                                "new_fact_revealed": "双方因邻里噪音问题发生口角",
                                "is_stage_completed": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        yield mock


def _populate_test_db():
    _remove_test_db()
    models.Base.metadata.drop_all(bind=_db_engine)
    models.Base.metadata.create_all(bind=_db_engine)

    db = SessionLocal()
    db.add(models.User(username="maintainer", hashed_password=hash_password("123456"), role="maintainer"))
    db.add(models.User(username="admin", hashed_password=hash_password("123456"), role="admin"))
    db.add(models.User(username="student001", hashed_password=hash_password("123456"), role="student"))
    db.add(models.User(username="student002", hashed_password=hash_password("123456"), role="student"))

    case = models.Case(
        title="邻里纠纷测试案件",
        case_type="邻里纠纷",
        background="张某与李某因楼道堆放杂物发生口角，进而引发肢体冲突。",
        original_content="原始案件文本",
        structured_data=json.dumps(
            {
                "case_name": "邻里纠纷测试案件",
                "case_type": "邻里纠纷",
                "full_narrative": "张某与李某因楼道堆放杂物发生口角，进而引发肢体冲突。",
                "fact_sheet": {
                    "case_time": "2026年5月10日上午9时",
                    "case_location": "某小区3号楼502室门前楼道",
                    "report_time": "2026年5月10日上午9时30分",
                    "timeline": [
                        {"time": "9:00", "event": "张某出门发现楼道被李某堆放杂物堵塞"},
                        {"time": "9:05", "event": "张某敲李某家门理论，李某开门后双方发生口角"},
                        {"time": "9:10", "event": "争吵升级为肢体冲突"},
                        {"time": "9:30", "event": "张某报警"},
                    ],
                },
                "persons": [
                    {
                        "name": "张某",
                        "role": "报警人",
                        "personality": "急躁、较真",
                        "speaking_style": "口语化、激动",
                        "init_emotion": 80,
                        "init_trust": 30,
                        "status": "报警人",
                    },
                    {
                        "name": "李某",
                        "role": "被投诉人",
                        "personality": "固执、防御性强",
                        "speaking_style": "生硬、爱辩解",
                        "init_emotion": 60,
                        "init_trust": 20,
                        "status": "被投诉人",
                    },
                ],
                "conflict_points": ["楼道公共区域使用权", "李某堆放杂物", "肢体冲突"],
                "key_facts": ["张某先敲门", "李某开门后辱骂", "张某报警"],
                "hidden_info": ["李某堆放杂物的时间", "是否有证人"],
            },
            ensure_ascii=False,
        ),
    )
    db.add(case)
    db.flush()

    scene = models.Scene(
        case_id=case.id,
        name="接警对话训练",
        description="模拟接警场景，训练民警接警时快速获取关键信息的能力。",
        difficulty="中等",
        dispatch_brief="接群众报警称小区楼道内发生纠纷，请立即前往处置。",
        first_impression="到达现场时，报警人张某情绪激动，李某家大门紧闭。",
        stages=json.dumps(
            [
                {
                    "stage_name": "初始接触",
                    "stage_goal": "安抚报警人情绪，了解基本事件情况",
                    "goal": "安抚报警人情绪，了解基本事件情况",
                },
                {
                    "stage_name": "信息收集",
                    "stage_goal": "详细了解事发经过，获取关键事实和证人信息",
                    "goal": "详细了解事发经过，获取关键事实和证人信息",
                },
                {
                    "stage_name": "核实调解",
                    "stage_goal": "核实对方情况，尝试调解",
                    "goal": "核实对方情况，尝试调解",
                },
            ],
            ensure_ascii=False,
        ),
    )
    db.add(scene)
    db.flush()

    role = models.Role(
        case_id=case.id,
        scene_id=scene.id,
        name="张某",
        role_type="报警人",
        personality="急躁、较真、容易情绪化",
        speaking_style="口语化、激动、语速快",
        init_emotion=80,
        init_trust=30,
        status="报警人",
        iq_level="中等",
        eq_level="一般",
        lying_ability="一般",
        weakness="涉及家人时会软化",
        knows_facts=json.dumps(
            ["李某长期在楼道堆放杂物", "今天早上出门时发现杂物堵塞通道", "敲李某家门后遭辱骂", "双方有过推搡"],
            ensure_ascii=False,
        ),
        does_not_know=json.dumps(["李某堆放杂物的具体时间", "是否有其他邻居目击"], ensure_ascii=False),
        hidden_truths=json.dumps(["之前也和李某有过几次小摩擦", "自己推搡中先动了手"], ensure_ascii=False),
    )
    db.add(role)
    db.flush()

    scene_role = models.SceneRole(scene_id=scene.id, role_id=role.id, is_primary=True)
    db.add(scene_role)

    role_li = models.Role(
        case_id=case.id,
        scene_id=scene.id,
        name="李某",
        role_type="被投诉人",
        personality="固执、防御性强",
        speaking_style="生硬、爱辩解",
        init_emotion=60,
        init_trust=20,
        status="被投诉人",
        iq_level="中等",
        eq_level="一般",
        lying_ability="一般",
        weakness="被当众指责时会激动",
        knows_facts=json.dumps(["杂物是自己放的", "认为楼道属于自己使用"], ensure_ascii=False),
        does_not_know=json.dumps(["张某是否先动手"], ensure_ascii=False),
        hidden_truths=json.dumps(["之前与物业也有矛盾"], ensure_ascii=False),
    )
    db.add(role_li)
    db.flush()
    db.add(models.SceneRole(scene_id=scene.id, role_id=role_li.id, is_primary=False))
    db.commit()
    db.close()


_populate_test_db()


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client(db_session):
    from main import app

    def _test_get_db():
        return db_session

    app.dependency_overrides[get_db] = _test_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def admin_token(client):
    response = client.post("/auth/token", data={"username": "admin", "password": "123456"})
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def maintainer_token(client):
    response = client.post("/auth/token", data={"username": "maintainer", "password": "123456"})
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def student_token(client):
    response = client.post("/auth/token", data={"username": "student001", "password": "123456"})
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def maintainer_headers(maintainer_token):
    return {"Authorization": f"Bearer {maintainer_token}"}


@pytest.fixture(scope="module")
def student_headers(student_token):
    return {"Authorization": f"Bearer {student_token}"}
