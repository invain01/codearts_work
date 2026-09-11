from sqlalchemy import func

from models import AuditLog, Category, Claim, FoundItem, LostItem, User, db


def stats():
    return {
        "users": User.query.count(),
        "lost": LostItem.query.filter(LostItem.status != "removed").count(),
        "found": FoundItem.query.filter(FoundItem.status != "removed").count(),
        "claims": Claim.query.count(),
        "closed": FoundItem.query.filter_by(status="closed").count()
        + LostItem.query.filter_by(status="closed").count(),
    }


def category_distribution():
    return (
        db.session.query(Category.name, func.count(FoundItem.id))
        .outerjoin(FoundItem, FoundItem.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort, Category.id)
        .all()
    )


def add_category(name):
    name = (name or "").strip()
    if not name:
        return "分类名称不能为空"
    if Category.query.filter_by(name=name).first():
        return "该分类已存在"
    db.session.add(Category(name=name))
    db.session.commit()
    return None


def list_items(item_type, keyword="", status=""):
    model = LostItem if item_type == "lost" else FoundItem
    query = model.query
    if keyword:
        query = query.filter(model.title.like(f"%{keyword}%"))
    if status:
        query = query.filter(model.status == status)
    return query.order_by(model.create_time.desc()).all()


def log(operator, action, target=""):
    db.session.add(AuditLog(operator_id=operator.id, action=action, target=target))
    db.session.commit()
