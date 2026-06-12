"""
Avatar assignment service.
Maps a role's age + gender to one of the 20 pixel-art avatars.
"""
import json
from typing import Optional

from database import SessionLocal
from models import AvatarImage

# Counts per (gender, age_group) slot
SLOT_COUNT = 5


def _safe_json_loads(value, default=None):
    if value in (None, "", "{}"):
        return default or {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default or {}


def _age_to_group(age: Optional[int]) -> str:
    """Map age number to age group string."""
    if age is None:
        return "young"  # default
    if age <= 35:
        return "young"
    if age <= 55:
        return "middle"
    return "old"


def _deterministic_index(name: str, pool_size: int) -> int:
    """Deterministic hash of name to pick within a pool."""
    h = sum(ord(c) for c in name) + len(name) * 7
    return h % pool_size


def assign_avatar(age: Optional[int], gender: Optional[str], name: str) -> int:
    """
    Pick the best-matching avatar_id for a role.

    Args:
        age: Role age from persona_meta (can be None).
        gender: Role gender from persona_meta (can be None).
        name: Role name, used as deterministic tiebreaker.

    Returns:
        avatar_id (1-20) that best matches the role.
    """
    age_group = _age_to_group(age)
    norm_gender = (gender or "").strip().lower()

    # Normalize gender
    if norm_gender in ("男", "male", "m"):
        norm_gender = "male"
    elif norm_gender in ("女", "female", "f"):
        norm_gender = "female"
    else:
        norm_gender = ""

    # Query matching avatars
    db = SessionLocal()
    try:
        if norm_gender:
            candidates = (
                db.query(AvatarImage)
                .filter(AvatarImage.gender == norm_gender, AvatarImage.age_group == age_group)
                .all()
            )
        else:
            candidates = db.query(AvatarImage).filter(AvatarImage.age_group == age_group).all()

        if not candidates:
            # Fallback: any avatar
            candidates = db.query(AvatarImage).all()

        if not candidates:
            return 1  # hard fallback

        idx = _deterministic_index(name, len(candidates))
        return candidates[idx].id
    finally:
        db.close()


def get_avatar_url(avatar_id: int) -> str:
    """Build the static-file URL for an avatar_id."""
    return f"/avatars/avatar_{avatar_id:02d}.svg"
