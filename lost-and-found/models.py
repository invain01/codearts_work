from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

CST = timezone(timedelta(hours=8))


def now_cst():
    return datetime.now(CST).replace(tzinfo=None)

ITEM_STATUS = {
    "lost": {"open": "寻找中", "closed": "已找回", "removed": "已下架"},
    "found": {"open": "待认领", "closed": "已归还", "removed": "已下架"},
}

CLAIM_STATUS = {"pending": "待审核", "approved": "已通过", "rejected": "已拒绝"}


class User(db.Model):
    __tablename__ = "t_user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    contact = db.Column(db.String(100), default="")
    create_time = db.Column(db.DateTime, default=now_cst)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class Category(db.Model):
    __tablename__ = "t_category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    sort = db.Column(db.Integer, default=0)


class LostItem(db.Model):
    __tablename__ = "t_lost_item"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("t_user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("t_category.id"))
    title = db.Column(db.String(100), nullable=False)
    lost_time = db.Column(db.Date)
    place = db.Column(db.String(100), default="")
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="open")
    create_time = db.Column(db.DateTime, default=now_cst)

    owner = db.relationship("User", foreign_keys=[user_id])
    category = db.relationship("Category")


class FoundItem(db.Model):
    __tablename__ = "t_found_item"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("t_user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("t_category.id"))
    title = db.Column(db.String(100), nullable=False)
    found_time = db.Column(db.Date)
    place = db.Column(db.String(100), default="")
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="open")
    create_time = db.Column(db.DateTime, default=now_cst)

    owner = db.relationship("User", foreign_keys=[user_id])
    category = db.relationship("Category")


class ItemImage(db.Model):
    __tablename__ = "t_item_image"

    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(10), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    path = db.Column(db.String(255), nullable=False)


class Claim(db.Model):
    __tablename__ = "t_claim"

    id = db.Column(db.Integer, primary_key=True)
    found_item_id = db.Column(
        db.Integer, db.ForeignKey("t_found_item.id"), nullable=False
    )
    applicant_id = db.Column(db.Integer, db.ForeignKey("t_user.id"), nullable=False)
    feature_desc = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    auditor_id = db.Column(db.Integer, db.ForeignKey("t_user.id"))
    create_time = db.Column(db.DateTime, default=now_cst)
    audit_time = db.Column(db.DateTime)

    found_item = db.relationship("FoundItem", foreign_keys=[found_item_id])
    applicant = db.relationship("User", foreign_keys=[applicant_id])
    auditor = db.relationship("User", foreign_keys=[auditor_id])


class Notification(db.Model):
    __tablename__ = "t_notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("t_user.id"), nullable=False)
    content = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=now_cst)


class AuditLog(db.Model):
    __tablename__ = "t_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey("t_user.id"))
    action = db.Column(db.String(50), nullable=False)
    target = db.Column(db.String(100), default="")
    create_time = db.Column(db.DateTime, default=now_cst)
