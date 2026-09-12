import os
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import Config
from models import CLAIM_STATUS, ITEM_STATUS, Category, User, db
from services import (
    admin_service,
    claim_service,
    item_service,
    notification_service,
    user_service,
)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DEFAULT_CATEGORIES = [
    "证件/卡类",
    "电子产品",
    "书籍资料",
    "衣物配饰",
    "运动器材",
    "生活用品",
    "其他",
]


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("请先登录", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    user = current_user()
    return {
        "current_user": user,
        "unread_count": notification_service.unread_count(user) if user else 0,
        "nav_categories": item_service.list_categories(),
        "ITEM_STATUS": ITEM_STATUS,
        "CLAIM_STATUS": CLAIM_STATUS,
    }


@app.route("/")
def index():
    latest_lost = item_service.search_items(
        item_service.ItemQuery(item_type="lost", per_page=6)
    ).items
    latest_found = item_service.search_items(
        item_service.ItemQuery(item_type="found", per_page=6)
    ).items
    return render_template(
        "index.html",
        latest_lost=latest_lost,
        latest_found=latest_found,
        stats=admin_service.stats(),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user, error = user_service.register(
            (request.form.get("username") or "").strip(),
            request.form.get("password") or "",
            (request.form.get("contact") or "").strip(),
        )
        if error:
            flash(error, "danger")
        else:
            session["user_id"] = user.id
            flash("注册成功，欢迎使用拾光", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = user_service.authenticate(
            (request.form.get("username") or "").strip(),
            request.form.get("password") or "",
        )
        if user:
            session["user_id"] = user.id
            flash("登录成功", "success")
            next_url = request.args.get("next", "")
            return redirect(next_url if next_url.startswith("/") else url_for("index"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "info")
    return redirect(url_for("index"))


@app.route("/items")
def items():
    item_type = request.args.get("type", "lost")
    if item_type not in ("lost", "found"):
        item_type = "lost"
    filters = item_service.ItemQuery(
        item_type=item_type,
        keyword=(request.args.get("q") or "").strip(),
        category_id=request.args.get("category", type=int),
        place=(request.args.get("place") or "").strip(),
        date_from=(request.args.get("date_from") or "").strip(),
        date_to=(request.args.get("date_to") or "").strip(),
        page=request.args.get("page", 1, type=int),
    )
    pagination = item_service.search_items(filters)
    return render_template(
        "items/list.html",
        item_type=item_type,
        pagination=pagination,
        filters=filters,
    )


@app.route("/item/<item_type>/<int:item_id>")
def item_detail(item_type, item_id):
    if item_type not in ("lost", "found"):
        abort(404)
    item = item_service.get_item(item_type, item_id)
    user = current_user()
    if not item or (item.status == "removed" and not (user and user.is_admin)):
        abort(404)
    images = item_service.get_images(item_type, item_id)
    matches = (
        item_service.suggest_matches(item)
        if item_type == "lost" and item.status == "open"
        else []
    )
    claims = claim_service.claims_of_item(item_id) if item_type == "found" else []
    return render_template(
        "items/detail.html",
        item=item,
        item_type=item_type,
        images=images,
        matches=matches,
        claims=claims,
    )


@app.route("/publish/<item_type>", methods=["GET", "POST"])
@login_required
def publish(item_type):
    if item_type not in ("lost", "found"):
        abort(404)
    if request.method == "POST":
        item = item_service.create_item(
            item_type,
            current_user(),
            request.form,
            request.files.getlist("images"),
        )
        if not item:
            flash("请填写物品名称", "danger")
            return redirect(url_for("publish", item_type=item_type))
        flash("发布成功", "success")
        return redirect(
            url_for("item_detail", item_type=item_type, item_id=item.id)
        )
    return render_template("items/form.html", item_type=item_type)


@app.route("/item/<item_type>/<int:item_id>/close", methods=["POST"])
@login_required
def close_item(item_type, item_id):
    item = item_service.get_item(item_type, item_id)
    if not item:
        abort(404)
    user = current_user()
    if item.user_id != user.id and not user.is_admin:
        abort(403)
    item_service.set_status(item_type, item_id, "closed")
    admin_service.log(user, "close", f"{item_type}:{item_id}")
    flash("已标记为完成", "success")
    return redirect(url_for("item_detail", item_type=item_type, item_id=item_id))


@app.route("/my/items")
@login_required
def my_items():
    lost_items, found_items = item_service.my_items(current_user())
    return render_template(
        "items/mine.html", lost_items=lost_items, found_items=found_items
    )


@app.route("/claim/<int:found_id>", methods=["POST"])
@login_required
def submit_claim(found_id):
    item = item_service.get_item("found", found_id)
    if not item:
        abort(404)
    claim, error = claim_service.submit_claim(
        current_user(), item, (request.form.get("feature_desc") or "").strip()
    )
    flash(error or "认领申请已提交，请等待审核", "danger" if error else "success")
    return redirect(url_for("item_detail", item_type="found", item_id=found_id))


@app.route("/claims")
@login_required
def my_claims():
    return render_template(
        "claims.html",
        applied=claim_service.my_claims(current_user()),
        received=claim_service.received_claims(current_user()),
    )


@app.route("/claim/<int:claim_id>/audit", methods=["POST"])
@login_required
def audit_claim(claim_id):
    claim = claim_service.get_claim(claim_id)
    if not claim:
        abort(404)
    user = current_user()
    if claim.found_item.user_id != user.id and not user.is_admin:
        abort(403)
    approve = request.form.get("action") == "approve"
    error = claim_service.audit_claim(user, claim, approve)
    if error:
        flash(error, "warning")
    else:
        flash("已通过认领" if approve else "已拒绝认领", "success")
        admin_service.log(user, "audit_claim", f"claim:{claim_id}")
    return redirect(url_for("my_claims"))


@app.route("/notifications")
@login_required
def notifications():
    user = current_user()
    notification_service.mark_all_read(user)
    return render_template(
        "notifications.html", notifications=notification_service.list_for(user)
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        user_service.update_contact(user, (request.form.get("contact") or "").strip())
        flash("联系方式已更新", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/admin")
@admin_required
def admin():
    return render_template(
        "admin.html",
        stats=admin_service.stats(),
        categories=item_service.list_categories(),
        distribution=admin_service.category_distribution(),
        lost_items=admin_service.list_items("lost"),
        found_items=admin_service.list_items("found"),
    )


@app.route("/admin/category", methods=["POST"])
@admin_required
def add_category():
    error = admin_service.add_category(request.form.get("name"))
    flash(error or "分类已添加", "danger" if error else "success")
    return redirect(url_for("admin"))


@app.route("/admin/item/<item_type>/<int:item_id>/remove", methods=["POST"])
@admin_required
def remove_item(item_type, item_id):
    if item_type not in ("lost", "found"):
        abort(404)
    item = item_service.set_status(item_type, item_id, "removed")
    if not item:
        abort(404)
    admin_service.log(current_user(), "remove_item", f"{item_type}:{item_id}")
    flash("已下架该信息", "success")
    return redirect(url_for("admin"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="没有权限访问该页面"), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="页面或资源不存在"), 404


def seed_defaults():
    if not Category.query.first():
        for sort_order, category_name in enumerate(DEFAULT_CATEGORIES):
            db.session.add(Category(name=category_name, sort=sort_order))
    if not User.query.filter_by(username="admin").first():
        admin_user = User(
            username="admin", role="admin", contact="admin@example.com"
        )
        admin_user.set_password("admin123")
        db.session.add(admin_user)
    db.session.commit()


@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    seed_defaults()
    app.logger.info("数据库初始化完成")


with app.app_context():
    db.create_all()
    seed_defaults()


if __name__ == "__main__":
    app.run(debug=True)
