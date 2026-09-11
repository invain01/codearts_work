from models import Notification, db


def notify(user_id, content):
    db.session.add(Notification(user_id=user_id, content=content))
    db.session.commit()


def list_for(user):
    return (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.create_time.desc())
        .all()
    )


def unread_count(user):
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def mark_all_read(user):
    Notification.query.filter_by(user_id=user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
