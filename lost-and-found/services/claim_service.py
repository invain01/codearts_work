from datetime import datetime

from models import Claim, FoundItem, db
from services import notification_service


def get_claim(claim_id):
    return db.session.get(Claim, claim_id)


def submit_claim(user, found_item, feature_desc):
    if found_item.status != "open":
        return None, "该物品已不可认领"
    if found_item.user_id == user.id:
        return None, "不能认领自己发布的物品"
    if not feature_desc:
        return None, "请填写物品特征说明"
    exists = Claim.query.filter_by(
        found_item_id=found_item.id, applicant_id=user.id, status="pending"
    ).first()
    if exists:
        return None, "你已提交过申请，请等待审核"
    claim = Claim(
        found_item_id=found_item.id,
        applicant_id=user.id,
        feature_desc=feature_desc,
    )
    db.session.add(claim)
    notification_service.notify(
        found_item.user_id,
        f"有人申请认领你发布的「{found_item.title}」，请及时处理。",
    )
    db.session.commit()
    return claim, None


def audit_claim(operator, claim, approve):
    if claim.status != "pending":
        return "该申请已处理"
    now = datetime.now()
    title = claim.found_item.title
    claim.status = "approved" if approve else "rejected"
    claim.auditor_id = operator.id
    claim.audit_time = now
    if approve:
        claim.found_item.status = "closed"
        others = Claim.query.filter(
            Claim.found_item_id == claim.found_item_id,
            Claim.id != claim.id,
            Claim.status == "pending",
        ).all()
        for other in others:
            other.status = "rejected"
            other.auditor_id = operator.id
            other.audit_time = now
            notification_service.notify(
                other.applicant_id, f"「{title}」已被他人认领，你的申请未通过。"
            )
        notification_service.notify(
            claim.applicant_id,
            f"你对「{title}」的认领申请已通过，请联系发布者领取。",
        )
    else:
        notification_service.notify(
            claim.applicant_id, f"你对「{title}」的认领申请未通过。"
        )
    db.session.commit()
    return None


def my_claims(user):
    return (
        Claim.query.filter_by(applicant_id=user.id)
        .order_by(Claim.create_time.desc())
        .all()
    )


def received_claims(user):
    return (
        Claim.query.join(FoundItem, Claim.found_item_id == FoundItem.id)
        .filter(FoundItem.user_id == user.id)
        .order_by(Claim.create_time.desc())
        .all()
    )


def claims_of_item(found_item_id):
    return (
        Claim.query.filter_by(found_item_id=found_item_id)
        .order_by(Claim.create_time.desc())
        .all()
    )
