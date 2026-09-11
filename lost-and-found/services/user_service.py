from models import User, db


def register(username, password, contact=""):
    if not username or not password:
        return None, "用户名和密码不能为空"
    if len(username) < 3 or len(username) > 20:
        return None, "用户名长度需为 3~20 个字符"
    if len(password) < 6:
        return None, "密码至少 6 位"
    if User.query.filter_by(username=username).first():
        return None, "用户名已存在"
    user = User(username=username, contact=contact)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, None


def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None


def update_contact(user, contact):
    user.contact = contact
    db.session.commit()
    return user
