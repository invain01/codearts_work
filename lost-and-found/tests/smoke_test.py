"""冒烟测试：覆盖注册、发布、检索、认领、审核、通知、后台等核心流程。"""
import logging
import os
import sys
import tempfile

logging.basicConfig(level=logging.INFO, format="%(message)s")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

TMP_DIR = tempfile.mkdtemp(prefix="lostfound-test-")
os.environ["DATABASE_URI"] = "sqlite:///" + os.path.join(TMP_DIR, "test.db")
os.environ["UPLOAD_FOLDER"] = os.path.join(TMP_DIR, "uploads")

import app as app_module  # noqa: E402
from models import Claim, FoundItem, Notification, User, db  # noqa: E402

app = app_module.app
client = app.test_client()


def test_home_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "拾光" in resp.get_data(as_text=True)


def test_full_flow():
    # 1. 卖家注册并发布招领
    resp = client.post(
        "/register",
        data={"username": "seller", "password": "123456", "contact": "13800000000"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp = client.post(
        "/publish/found",
        data={
            "title": "黑色雨伞",
            "category_id": "1",
            "item_time": "2026-09-10",
            "place": "图书馆一楼",
            "description": "伞柄有磨损",
        },
        follow_redirects=True,
    )
    assert "发布成功" in resp.get_data(as_text=True)

    with app.app_context():
        item = FoundItem.query.filter_by(title="黑色雨伞").first()
        assert item is not None
        found_id = item.id

    # 2. 买家注册并提交认领
    client.get("/logout")
    client.post(
        "/register",
        data={"username": "buyer", "password": "123456", "contact": "13900000000"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/claim/{found_id}",
        data={"feature_desc": "伞骨有一处补丁，伞套内侧写了名字"},
        follow_redirects=True,
    )
    assert "认领申请已提交" in resp.get_data(as_text=True)

    # 3. 卖家审核通过
    client.get("/logout")
    client.post("/login", data={"username": "seller", "password": "123456"})
    with app.app_context():
        claim = Claim.query.filter_by(found_item_id=found_id).first()
        assert claim is not None
        claim_id = claim.id
    resp = client.post(
        f"/claim/{claim_id}/audit",
        data={"action": "approve"},
        follow_redirects=True,
    )
    assert "已通过认领" in resp.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(FoundItem, found_id).status == "closed"
        buyer = User.query.filter_by(username="buyer").first()
        assert Notification.query.filter_by(user_id=buyer.id).count() >= 1

    # 4. 管理员登录并访问后台
    client.get("/logout")
    client.post("/login", data={"username": "admin", "password": "admin123"})
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "管理后台" in resp.get_data(as_text=True)


def test_search_and_filter():
    resp = client.get("/items?type=found&q=雨伞")
    assert resp.status_code == 200
    assert "黑色雨伞" in resp.get_data(as_text=True)


def test_permission_denied():
    client.get("/logout")
    resp = client.get("/admin")
    assert resp.status_code == 403


def main():
    tests = [
        test_home_page,
        test_full_flow,
        test_search_and_filter,
        test_permission_denied,
    ]
    for test in tests:
        test()
        logging.info("PASS %s", test.__name__)
    logging.info("全部通过（%d 项）", len(tests))


if __name__ == "__main__":
    main()
