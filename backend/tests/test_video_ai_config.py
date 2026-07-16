import io

import models
from routers import videos as videos_router
from services import video_auto_config_service


def test_video_analysis_uses_dedicated_provider_settings(monkeypatch):
    captured = {}

    def fake_binding(*, provider, model):
        captured.update(provider=provider, model=model)
        return object(), model, provider, "test-key"

    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "qwen")
    monkeypatch.setenv("VIDEO_ANALYSIS_MODEL", "qwen-plus")
    monkeypatch.setattr(
        "services.llm_provider.get_chat_completion_binding",
        fake_binding,
    )

    _, model, provider, api_key = video_auto_config_service._get_video_analysis_llm()

    assert captured == {"provider": "qwen", "model": "qwen-plus"}
    assert provider == "qwen"
    assert model == "qwen-plus"
    assert api_key == "test-key"


def test_video_analysis_reports_missing_ffmpeg_before_external_calls(monkeypatch):
    monkeypatch.setattr(video_auto_config_service, "_ffmpeg_available", lambda: False)
    monkeypatch.setattr(
        video_auto_config_service,
        "_get_video_analysis_llm",
        lambda: (object(), "qwen-plus", "qwen", "test-key"),
    )

    payload = video_auto_config_service.analyze_video_file("sample.mp4", title_hint="测试视频")

    assert payload["analysis_mode"] == "error"
    assert "ffmpeg" in payload["analysis_error"]


def _fake_analysis(title: str = "AI识别后标题") -> dict:
    return {
        "analysis_mode": "llm_vision",
        "title": title,
        "description": "AI 已自动识别视频内容并生成配置。",
        "video_type": "interactive",
        "briefing": "自动生成的训练简报",
        "tags": ["自动导入", "AI识别"],
        "status": "draft",
        "suggested_timestamps": [12],
        "node_generation_mode": "llm_generated",
        "nodes": [
            {
                "title": "AI 节点 1",
                "trigger_time": 12,
                "pause_mode": "auto_pause",
                "timeout_seconds": 30,
                "retry_score_deduct": 5,
                "skip_score_deduct": 15,
                "prop_mode": "manual",
                "node_type": "action",
                "required_gesture": "show_id",
                "required_keywords": ["民警", "配合检查"],
                "score_weight": 10,
                "prompt_content": {
                    "instruction": "请出示证件并说明身份",
                    "prop_label": "执法证件",
                },
                "node_config": {
                    "pass_rule": {"mode": "all"},
                    "speech_rule": {"match_mode": "any", "min_count": 1, "min_length": 0},
                },
            }
        ],
    }


def test_upload_video_auto_configures_with_ai(client, admin_headers, monkeypatch, tmp_path):
    videos_root = tmp_path / "videos"
    thumbs_root = tmp_path / "thumbs"
    videos_root.mkdir(parents=True, exist_ok=True)
    thumbs_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(videos_router, "VIDEOS_DIR", str(videos_root))
    monkeypatch.setattr(videos_router, "THUMBNAILS_DIR", str(thumbs_root))
    monkeypatch.setattr(videos_router, "_ensure_video_thumbnail", lambda video, db: None)
    monkeypatch.setattr(
        videos_router.video_auto_config_service,
        "analyze_video_file",
        lambda *args, **kwargs: _fake_analysis(),
    )

    response = client.post(
        "/videos/upload",
        headers=admin_headers,
        data={
            "title": "原始上传标题",
            "video_type": "teaching",
            "auto_configure": "true",
        },
        files={"file": ("sample.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "AI识别后标题"
    assert payload["video_type"] == "teaching"
    assert payload["briefing"] == "自动生成的训练简报"
    assert payload["node_count"] >= 1
    assert payload["nodes"][0]["title"] == "AI 节点 1"


def test_upload_video_respects_manual_interactive_type(client, admin_headers, monkeypatch, tmp_path):
    videos_root = tmp_path / "videos-manual"
    thumbs_root = tmp_path / "thumbs-manual"
    videos_root.mkdir(parents=True, exist_ok=True)
    thumbs_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(videos_router, "VIDEOS_DIR", str(videos_root))
    monkeypatch.setattr(videos_router, "THUMBNAILS_DIR", str(thumbs_root))
    monkeypatch.setattr(videos_router, "_ensure_video_thumbnail", lambda video, db: None)
    monkeypatch.setattr(
        videos_router.video_auto_config_service,
        "analyze_video_file",
        lambda *args, **kwargs: {
            **_fake_analysis(),
            "video_type": "teaching",
            "nodes": [],
        },
    )

    response = client.post(
        "/videos/upload",
        headers=admin_headers,
        data={
            "title": "手动选择实训",
            "video_type": "interactive",
            "auto_configure": "true",
        },
        files={"file": ("sample.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["video_type"] == "interactive"
    assert payload["node_count"] >= 1


def test_admin_can_rebuild_video_config_with_ai(client, db_session, admin_headers, monkeypatch):
    video = models.TrainingVideo(
        title="待识别视频",
        description="旧描述",
        video_type="teaching",
        file_path="existing.mp4",
        duration=88,
        status="draft",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    monkeypatch.setattr(videos_router, "VIDEOS_DIR", ".")
    monkeypatch.setattr(videos_router, "_ensure_video_thumbnail", lambda video, db: None)
    monkeypatch.setattr(videos_router.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        videos_router.video_auto_config_service,
        "analyze_video_file",
        lambda *args, **kwargs: _fake_analysis(title="AI重建标题"),
    )

    response = client.post(
        f"/videos/{video.id}/auto-configure",
        json={"overwrite_meta": True, "overwrite_nodes": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "AI重建标题"
    assert payload["node_count"] == 1
    assert payload["auto_analysis"]["analysis_mode"] == "llm_vision"
    assert payload["auto_analysis"]["suggested_timestamps"] == [12]


def test_admin_rebuild_respects_preferred_interactive_type(client, db_session, admin_headers, monkeypatch):
    video = models.TrainingVideo(
        title="重建互动实训",
        description="旧描述",
        video_type="teaching",
        file_path="existing.mp4",
        duration=88,
        status="draft",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    monkeypatch.setattr(videos_router, "VIDEOS_DIR", ".")
    monkeypatch.setattr(videos_router, "_ensure_video_thumbnail", lambda video, db: None)
    monkeypatch.setattr(videos_router.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        videos_router.video_auto_config_service,
        "analyze_video_file",
        lambda *args, **kwargs: {
            **_fake_analysis(title="强制重建互动"),
            "video_type": "teaching",
            "nodes": [],
        },
    )

    response = client.post(
        f"/videos/{video.id}/auto-configure",
        json={"overwrite_meta": True, "overwrite_nodes": True, "preferred_type": "interactive"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["video_type"] == "interactive"
    assert payload["node_count"] >= 1
    assert payload["auto_analysis"]["suggested_timestamps"]


def test_admin_can_delete_video_without_server_error(client, db_session, admin_headers, monkeypatch):
    video = models.TrainingVideo(
        title="待删除视频",
        description="删除测试",
        video_type="interactive",
        file_path="delete-me.mp4",
        thumbnail_path="delete-me.jpg",
        duration=30,
        status="draft",
    )
    db_session.add(video)
    db_session.flush()
    db_session.add(
        models.VideoNode(
            video_id=video.id,
            node_index=0,
            title="删除节点",
            trigger_time=10,
            node_type="action",
        )
    )
    db_session.commit()

    monkeypatch.setattr(videos_router.os.path, "exists", lambda path: False)

    response = client.delete(f"/videos/{video.id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["video_id"] == video.id
    assert db_session.query(models.TrainingVideo).filter_by(id=video.id).first() is None


def test_police_incident_fallback_generates_structured_nodes():
    payload = video_auto_config_service.analyze_video_file(
        "missing-file.mp4",
        title_hint="\u5bb6\u5ead\u7ea0\u7eb7\u6a21\u62df\u8b66\u60c5",
        duration_seconds=180,
        preferred_type="interactive",
    )

    assert payload["video_type"] == "interactive"
    assert "\u6a21\u62df\u8b66\u60c5" in payload["tags"]
    assert len(payload["nodes"]) >= 4

    first_node = payload["nodes"][0]
    assert first_node["node_type"] == "voice_qa"
    assert first_node["node_config"]["police_node_type"]
    assert first_node["prompt_content"]["scene_summary"]
    assert first_node["prompt_content"]["police_question"]
    assert first_node["node_config"]["standard_points"]
    assert first_node["node_config"]["score_rubric"]["risk_awareness"] == 30


def test_police_scenario_hint_controls_template_variant_and_difficulty():
    payload = video_auto_config_service.analyze_video_file(
        "missing-file.mp4",
        title_hint="road-scene",
        duration_seconds=120,
        preferred_type="interactive",
        scenario_hint="traffic_scene",
        training_variant="exam",
        difficulty_level="advanced",
    )

    assert payload["video_type"] == "interactive"
    assert payload["police_scenario"] == "traffic_scene"
    assert payload["training_variant"] == "exam"
    assert payload["difficulty_level"] == "advanced"
    assert "交通现场处置" in payload["tags"]
    assert "考核版" in payload["tags"]
    assert payload["nodes"]
    assert all(node["timeout_seconds"] <= 60 for node in payload["nodes"])
    assert payload["nodes"][0]["node_config"]["police_scenario"] == "traffic_scene"
    assert payload["nodes"][0]["node_config"]["training_variant"] == "exam"
