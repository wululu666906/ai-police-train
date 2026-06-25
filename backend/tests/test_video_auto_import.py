import models
from routers import videos as videos_router


def test_admin_list_auto_imports_interactive_video_with_generated_nodes(
    client,
    db_session,
    admin_headers,
    monkeypatch,
    tmp_path,
):
    videos_root = tmp_path / "videos"
    auto_root = videos_root / "auto_upload" / "interactive"
    thumbnails_root = tmp_path / "thumbnails"
    auto_root.mkdir(parents=True, exist_ok=True)
    thumbnails_root.mkdir(parents=True, exist_ok=True)

    video_path = auto_root / "交通执法自动实训.mp4"
    video_path.write_bytes(b"fake video bytes")

    monkeypatch.setattr(videos_router, "VIDEOS_DIR", str(videos_root))
    monkeypatch.setattr(videos_router, "AUTO_IMPORT_DIR", str(videos_root / "auto_upload"))
    monkeypatch.setattr(videos_router, "THUMBNAILS_DIR", str(thumbnails_root))
    monkeypatch.setattr(videos_router, "_LAST_AUTO_IMPORT_SCAN_AT", 0.0)
    monkeypatch.setattr(
        videos_router,
        "_LAST_AUTO_IMPORT_SUMMARY",
        {
            "watched_dir": str(videos_root / "auto_upload"),
            "imported_count": 0,
            "skipped_count": 0,
            "detected_count": 0,
        },
    )
    monkeypatch.setattr(videos_router, "_probe_video_duration", lambda _: 96.0)
    monkeypatch.setattr(videos_router, "_ensure_video_thumbnail", lambda video, db: None)

    response = client.get("/videos/admin/list", headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["auto_import"]["imported_count"] == 1
    assert payload["auto_import"]["detected_count"] == 1

    video = (
        db_session.query(models.TrainingVideo)
        .filter(models.TrainingVideo.file_path == "auto_upload/interactive/交通执法自动实训.mp4")
        .first()
    )
    assert video is not None
    assert video.video_type == "interactive"
    assert video.duration == 96
    assert video.briefing
    assert "自动导入" in (video.tags or "")
    assert len(video.nodes) == 3
    assert any(node.required_gesture == "stop_signal" for node in video.nodes)
    assert any(node.required_gesture == "show_id" for node in video.nodes)
    assert any(node.node_type == "voice_qa" for node in video.nodes)
