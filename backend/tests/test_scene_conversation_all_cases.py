"""Ensure scene conversation pipeline applies to all speakable roles."""

from services.multi_role_service import should_use_scene_conversation


class _Role:
    def __init__(self, status: str = "正常"):
        self.status = status


def test_scene_conversation_enabled_for_single_role():
    assert should_use_scene_conversation([_Role()]) is True


def test_scene_conversation_disabled_without_speakable_role():
    assert should_use_scene_conversation([_Role(status="死亡")]) is False
