"""
Announcement endpoints for the High School Management System API
"""

from datetime import datetime, timezone
import re
import unicodedata
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=5, max_length=1000)
    starts_at: Optional[str] = None
    expires_at: str


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=120)
    message: Optional[str] = Field(default=None, min_length=5, max_length=1000)
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None


def _parse_iso_datetime(date_value: Optional[str], field_name: str) -> Optional[datetime]:
    if date_value is None:
        return None

    candidate = date_value.strip()
    if not candidate:
        return None

    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be a valid ISO-8601 datetime"
        ) from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _to_iso_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _ensure_authenticated_teacher(username: Optional[str]) -> Dict[str, Any]:
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def _serialize_announcement(announcement: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(announcement)
    result["id"] = result.pop("_id")
    return result


def _slugify_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only.strip().lower())
    slug = slug.strip("-")
    if not slug:
        raise HTTPException(status_code=400, detail="title must contain letters or numbers")
    return slug


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all announcements that are currently active."""
    now = datetime.now(timezone.utc)
    announcements: List[Dict[str, Any]] = []

    for announcement in announcements_collection.find().sort("expires_at", 1):
        starts_at = _parse_iso_datetime(announcement.get("starts_at"), "starts_at")
        expires_at = _parse_iso_datetime(announcement.get("expires_at"), "expires_at")

        if expires_at is None:
            continue

        if starts_at and now < starts_at:
            continue

        if now > expires_at:
            continue

        announcements.append(_serialize_announcement(announcement))

    return announcements


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """List all announcements (active, scheduled, and expired) for management."""
    _ensure_authenticated_teacher(teacher_username)

    announcements = []
    for announcement in announcements_collection.find().sort("expires_at", 1):
        announcements.append(_serialize_announcement(announcement))

    return announcements


@router.post("", response_model=Dict[str, Any], status_code=201)
def create_announcement(
    payload: AnnouncementCreate,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement. Authentication required."""
    teacher = _ensure_authenticated_teacher(teacher_username)

    starts_at = _parse_iso_datetime(payload.starts_at, "starts_at")
    expires_at = _parse_iso_datetime(payload.expires_at, "expires_at")

    if expires_at is None:
        raise HTTPException(status_code=400, detail="expires_at is required")

    if starts_at and starts_at >= expires_at:
        raise HTTPException(status_code=400, detail="starts_at must be earlier than expires_at")

    announcement_id = _slugify_title(payload.title)

    announcement = {
        "_id": announcement_id,
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "starts_at": _to_iso_utc(starts_at),
        "expires_at": _to_iso_utc(expires_at),
        "created_by": teacher["username"]
    }

    try:
        announcements_collection.insert_one(announcement)
    except Exception as error:
        if "duplicate key" in str(error).lower():
            raise HTTPException(status_code=409, detail="Announcement title already exists") from error
        raise HTTPException(status_code=500, detail="Failed to create announcement") from error

    return _serialize_announcement(announcement)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpdate,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement. Authentication required."""
    _ensure_authenticated_teacher(teacher_username)

    existing = announcements_collection.find_one({"_id": announcement_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    update_data: Dict[str, Any] = {}

    if payload.title is not None:
        update_data["title"] = payload.title.strip()
    if payload.message is not None:
        update_data["message"] = payload.message.strip()

    current_starts_at = existing.get("starts_at")
    current_expires_at = existing.get("expires_at")

    starts_at = _parse_iso_datetime(
        payload.starts_at if payload.starts_at is not None else current_starts_at,
        "starts_at"
    )
    expires_at = _parse_iso_datetime(
        payload.expires_at if payload.expires_at is not None else current_expires_at,
        "expires_at"
    )

    if expires_at is None:
        raise HTTPException(status_code=400, detail="expires_at is required")

    if starts_at and starts_at >= expires_at:
        raise HTTPException(status_code=400, detail="starts_at must be earlier than expires_at")

    update_data["starts_at"] = _to_iso_utc(starts_at)
    update_data["expires_at"] = _to_iso_utc(expires_at)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    result = announcements_collection.update_one(
        {"_id": announcement_id},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        updated = announcements_collection.find_one({"_id": announcement_id})
        return _serialize_announcement(updated)

    updated = announcements_collection.find_one({"_id": announcement_id})
    return _serialize_announcement(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Delete an announcement. Authentication required."""
    _ensure_authenticated_teacher(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
