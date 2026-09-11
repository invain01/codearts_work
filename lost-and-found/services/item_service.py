import os
import uuid
from datetime import datetime
from difflib import SequenceMatcher

from flask import current_app
from sqlalchemy import or_, select

from models import Category, FoundItem, ItemImage, LostItem, db


def list_categories():
    return Category.query.order_by(Category.sort, Category.id).all()


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def search_items(
    item_type,
    keyword="",
    category_id=None,
    place="",
    date_from="",
    date_to="",
    page=1,
    per_page=8,
):
    model = LostItem if item_type == "lost" else FoundItem
    date_col = model.lost_time if item_type == "lost" else model.found_time
    stmt = select(model).where(model.status != "removed")
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(model.title.like(like), model.description.like(like)))
    if category_id:
        stmt = stmt.where(model.category_id == category_id)
    if place:
        stmt = stmt.where(model.place.like(f"%{place}%"))
    start = parse_date(date_from)
    end = parse_date(date_to)
    if start:
        stmt = stmt.where(date_col >= start)
    if end:
        stmt = stmt.where(date_col <= end)
    stmt = stmt.order_by(model.create_time.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def get_item(item_type, item_id):
    model = LostItem if item_type == "lost" else FoundItem
    return db.session.get(model, item_id)


def get_images(item_type, item_id):
    return ItemImage.query.filter_by(item_type=item_type, item_id=item_id).all()


def create_item(item_type, user, form, files):
    model = LostItem if item_type == "lost" else FoundItem
    title = (form.get("title") or "").strip()
    if not title:
        return None
    item = model(
        user_id=user.id,
        category_id=form.get("category_id", type=int),
        title=title,
        place=(form.get("place") or "").strip(),
        description=(form.get("description") or "").strip(),
        status="open",
    )
    item_time = parse_date((form.get("item_time") or "").strip())
    if item_type == "lost":
        item.lost_time = item_time
    else:
        item.found_time = item_time
    db.session.add(item)
    db.session.flush()
    save_images(item_type, item.id, files)
    db.session.commit()
    return item


def save_images(item_type, item_id, files):
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    allowed = current_app.config["ALLOWED_IMAGE_EXT"]
    os.makedirs(upload_folder, exist_ok=True)
    for file in files or []:
        filename = getattr(file, "filename", "") or ""
        if not filename:
            continue
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed:
            continue
        stored = uuid.uuid4().hex + ext
        file.save(os.path.join(upload_folder, stored))
        db.session.add(
            ItemImage(item_type=item_type, item_id=item_id, path=stored)
        )


def my_items(user):
    lost = (
        LostItem.query.filter_by(user_id=user.id)
        .order_by(LostItem.create_time.desc())
        .all()
    )
    found = (
        FoundItem.query.filter_by(user_id=user.id)
        .order_by(FoundItem.create_time.desc())
        .all()
    )
    return lost, found


def set_status(item_type, item_id, status):
    item = get_item(item_type, item_id)
    if item:
        item.status = status
        db.session.commit()
    return item


def suggest_matches(lost_item, limit=5):
    candidates = FoundItem.query.filter_by(
        category_id=lost_item.category_id, status="open"
    ).all()
    scored = []
    for candidate in candidates:
        score = SequenceMatcher(
            None, lost_item.title or "", candidate.title or ""
        ).ratio()
        if (
            lost_item.place
            and candidate.place
            and (
                lost_item.place in candidate.place
                or candidate.place in lost_item.place
            )
        ):
            score += 0.5
        if score >= 0.5:
            scored.append((score, candidate))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]
