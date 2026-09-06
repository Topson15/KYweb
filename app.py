#!/usr/bin/env python3
"""动态收录门户：分类 / 二级介绍 / 供需 / 广告 / 后台审核。"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    flash,
    abort,
)
from werkzeug.security import check_password_hash, generate_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "portal.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me-in-production")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            contact TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            intro TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(parent_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category_id INTEGER,
            kind TEXT NOT NULL DEFAULT 'supply',
            summary TEXT DEFAULT '',
            body TEXT DEFAULT '',
            contact TEXT DEFAULT '',
            website TEXT DEFAULT '',
            logo TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            featured INTEGER DEFAULT 0,
            expire_at TEXT,
            author_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(id),
            FOREIGN KEY(author_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_url TEXT NOT NULL,
            link_url TEXT DEFAULT '#',
            position TEXT NOT NULL DEFAULT 'home_banner',
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    db.commit()
    cur = db.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        seed(db)
    db.close()


def seed(db):
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO users(username,password_hash,role,contact,created_at) VALUES(?,?,?,?,?)",
        ("admin", generate_password_hash("admin123"), "admin", "@admin", now),
    )
    db.execute(
        "INSERT INTO users(username,password_hash,role,contact,created_at) VALUES(?,?,?,?,?)",
        ("demo", generate_password_hash("demo123"), "user", "@demo", now),
    )
    parents = [
        (None, "工具合集", "tools", "收录经人工筛选的效率工具与开放平台，注意甄别风险。", 1),
        (None, "供需资源", "demand", "发布合法的供应与需求信息，需审核后展示。", 2),
        (None, "曝光专栏", "reports", "仅收录可核验的公开信息与用户投诉摘要。", 3),
        (None, "实用工具", "utils", "站内常用计算器、格式转换与文档模板入口。", 4),
    ]
    for p in parents:
        db.execute(
            "INSERT INTO categories(parent_id,name,slug,intro,sort_order) VALUES(?,?,?,?,?)",
            p,
        )
    parent_ids = {r["slug"]: r["id"] for r in db.execute("SELECT id,slug FROM categories")}
    children = [
        ("tools", "常规接口", "api", "开放 API、Webhook、SDK 与文档索引。", 1),
        ("tools", "独立站", "indie", "独立开发者产品与小而美站点。", 2),
        ("tools", "设计资源", "design", "图标、字体、组件库与设计系统。", 3),
        ("tools", "开发框架", "framework", "前后端框架与脚手架。", 4),
        ("tools", "数据服务", "data", "公开数据集与分析面板。", 5),
        ("demand", "供应", "supply", "可提供的产品、服务或产能。", 1),
        ("demand", "求购", "buy", "明确预算与交付要求的采购信息。", 2),
        ("demand", "合作", "coop", "联合运营、渠道与技术合作。", 3),
        ("reports", "虚假宣传", "fake", "夸大承诺与无法兑现的案例摘要。", 1),
        ("reports", "服务纠纷", "dispute", "履约争议公开记录。", 2),
        ("utils", "格式转换", "convert", "文档与媒体格式转换入口。", 1),
        ("utils", "站点检测", "check", "可用性与基础安全检测。", 2),
    ]
    for parent_slug, name, slug, intro, order in children:
        db.execute(
            "INSERT INTO categories(parent_id,name,slug,intro,sort_order) VALUES(?,?,?,?,?)",
            (parent_ids[parent_slug], name, slug, intro, order),
        )
    cat = {r["slug"]: r["id"] for r in db.execute("SELECT id,slug FROM categories")}
    expire = (datetime.utcnow() + timedelta(days=180)).date().isoformat()
    listings = [
        (
            "巡航看板 · 数据监控套件",
            cat["api"],
            "supply",
            "面向运营团队的实时看板，支持多数据源接入。",
            "提供指标订阅、异常告警与周报导出。适合中小团队快速上线监控。",
            "@ops_demo",
            "https://example.com/dashboard",
            "",
            "approved",
            1,
        ),
        (
            "厅级内容分发服务",
            cat["indie"],
            "supply",
            "图文与短视频分发排期工具，支持多渠道。",
            "可按栏目自动排期，保留审核流。不承接违法内容。",
            "@media_demo",
            "https://example.com/media",
            "",
            "approved",
            1,
        ),
        (
            "灰软替代：开源投递助手",
            cat["framework"],
            "supply",
            "开源表单与素材投递工具，可自托管。",
            "完全本地部署，数据不出境。提供文档与二次开发接口。",
            "@oss_demo",
            "https://example.com/oss",
            "",
            "approved",
            1,
        ),
        (
            "平台履约担保说明（示例）",
            cat["coop"],
            "supply",
            "仅作流程演示：资金走合规托管，不承诺收益。",
            "本条为演示数据。真实业务需自行完成合规审查。",
            "@guard_demo",
            "https://example.com",
            "",
            "approved",
            1,
        ),
        (
            "求购：中小团队知识库搭建",
            cat["buy"],
            "demand",
            "需要可私有化部署的文档站，预算面议。",
            "要求支持 Markdown、权限分级与全文检索。",
            "@buyer01",
            "",
            "",
            "approved",
            0,
        ),
    ]
    for t, cid, kind, summary, body, contact, site, logo, status, feat in listings:
        db.execute(
            """INSERT INTO listings(title,category_id,kind,summary,body,contact,website,logo,status,featured,expire_at,author_id,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t, cid, kind, summary, body, contact, site, logo, status, feat, expire, 2, now),
        )
    ads = [
        ("顶栏广告 A", "https://placehold.co/580x70/2563eb/fff?text=Banner+A", "#", "home_banner", 1, 1),
        ("顶栏广告 B", "https://placehold.co/580x70/7c3aed/fff?text=Banner+B", "#", "home_banner", 1, 2),
        ("顶栏广告 C", "https://placehold.co/580x70/0f766e/fff?text=Banner+C", "#", "home_banner", 1, 3),
        ("顶栏广告 D", "https://placehold.co/580x70/b45309/fff?text=Banner+D", "#", "home_banner", 1, 4),
        ("侧栏招商", "https://placehold.co/300x90/111827/fff?text=Ad+Slot", "#", "sidebar", 1, 1),
    ]
    for a in ads:
        db.execute(
            "INSERT INTO ads(title,image_url,link_url,position,active,sort_order) VALUES(?,?,?,?,?,?)",
            a,
        )
    db.execute(
        "INSERT INTO notices(title,body,active,created_at) VALUES(?,?,?,?)",
        (
            "站点公告",
            "1. 本站只收录合法公开资源。\n2. 广告仅收取展示费，不对交易结果负责。\n3. 供需信息需审核后展示。\n4. 遇到纠纷请保留凭证联系客服。",
            1,
            now,
        ),
    )
    db.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("site_name", "收录站 Demo"))
    db.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("site_tagline", "让好资源被长期看见"))
    db.commit()


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


@app.context_processor
def inject():
    db = get_db()
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM settings")}
    parents = db.execute(
        "SELECT * FROM categories WHERE parent_id IS NULL ORDER BY sort_order"
    ).fetchall()
    children_map = {}
    for p in parents:
        children_map[p["id"]] = db.execute(
            "SELECT * FROM categories WHERE parent_id=? ORDER BY sort_order",
            (p["id"],),
        ).fetchall()
    return {
        "settings": settings,
        "nav_parents": parents,
        "nav_children": children_map,
        "user": current_user(),
        "now": datetime.utcnow(),
    }


@app.route("/")
def index():
    db = get_db()
    banners = db.execute(
        "SELECT * FROM ads WHERE position='home_banner' AND active=1 ORDER BY sort_order"
    ).fetchall()
    featured = db.execute(
        """SELECT l.*, c.name AS cat_name FROM listings l
           LEFT JOIN categories c ON c.id=l.category_id
           WHERE l.status='approved' AND l.featured=1
           ORDER BY l.id DESC LIMIT 8"""
    ).fetchall()
    tools_parent = db.execute("SELECT * FROM categories WHERE slug='tools'").fetchone()
    tool_cats = []
    tool_listings = []
    if tools_parent:
        tool_cats = db.execute(
            "SELECT * FROM categories WHERE parent_id=? ORDER BY sort_order",
            (tools_parent["id"],),
        ).fetchall()
        current_slug = request.args.get("cat") or (tool_cats[0]["slug"] if tool_cats else None)
        current = next((c for c in tool_cats if c["slug"] == current_slug), tool_cats[0] if tool_cats else None)
        if current:
            tool_listings = db.execute(
                """SELECT l.*, c.name AS cat_name FROM listings l
                   JOIN categories c ON c.id=l.category_id
                   WHERE l.status='approved' AND (l.category_id=? OR c.parent_id=?)
                   ORDER BY l.id DESC LIMIT 24""",
                (current["id"], current["id"]),
            ).fetchall()
    else:
        current = None
    notice = db.execute("SELECT * FROM notices WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    return render_template(
        "index.html",
        banners=banners,
        featured=featured,
        tool_cats=tool_cats,
        tool_listings=tool_listings,
        current_cat=current,
        notice=notice,
        tools_parent=tools_parent,
    )


@app.route("/c/<slug>")
def category(slug):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE slug=?", (slug,)).fetchone()
    if not cat:
        abort(404)
    children = db.execute(
        "SELECT * FROM categories WHERE parent_id=? ORDER BY sort_order", (cat["id"],)
    ).fetchall()
    parent = None
    if cat["parent_id"]:
        parent = db.execute("SELECT * FROM categories WHERE id=?", (cat["parent_id"],)).fetchone()
    listings = db.execute(
        """SELECT l.*, c.name AS cat_name FROM listings l
           JOIN categories c ON c.id=l.category_id
           WHERE l.status='approved' AND (l.category_id=? OR c.parent_id=?)
           ORDER BY l.featured DESC, l.id DESC""",
        (cat["id"], cat["id"]),
    ).fetchall()
    return render_template(
        "category.html", cat=cat, children=children, parent=parent, listings=listings
    )


@app.route("/item/<int:item_id>")
def item_detail(item_id):
    db = get_db()
    item = db.execute(
        """SELECT l.*, c.name AS cat_name, c.slug AS cat_slug FROM listings l
           LEFT JOIN categories c ON c.id=l.category_id WHERE l.id=?""",
        (item_id,),
    ).fetchone()
    if not item or (item["status"] != "approved" and (not current_user() or current_user()["role"] != "admin")):
        abort(404)
    return render_template("detail.html", item=item)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    rows = []
    if q:
        like = f"%{q}%"
        rows = (
            get_db()
            .execute(
                """SELECT l.*, c.name AS cat_name FROM listings l
                   LEFT JOIN categories c ON c.id=l.category_id
                   WHERE l.status='approved' AND (l.title LIKE ? OR l.summary LIKE ? OR l.body LIKE ?)
                   ORDER BY l.id DESC""",
                (like, like, like),
            )
            .fetchall()
        )
    return render_template("search.html", q=q, listings=rows)


@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    db = get_db()
    cats = db.execute(
        "SELECT * FROM categories WHERE parent_id IS NOT NULL ORDER BY parent_id, sort_order"
    ).fetchall()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("标题必填", "error")
            return redirect(url_for("submit"))
        db.execute(
            """INSERT INTO listings(title,category_id,kind,summary,body,contact,website,logo,status,featured,expire_at,author_id,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                title,
                request.form.get("category_id") or None,
                request.form.get("kind") or "supply",
                request.form.get("summary", ""),
                request.form.get("body", ""),
                request.form.get("contact", ""),
                request.form.get("website", ""),
                request.form.get("logo", ""),
                "pending",
                0,
                request.form.get("expire_at") or None,
                current_user()["id"],
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        flash("已提交，等待审核", "ok")
        return redirect(url_for("index"))
    return render_template("submit.html", cats=cats)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["uid"] = row["id"]
            dest = request.args.get("next") or (url_for("admin_home") if row["role"] == "admin" else url_for("index"))
            return redirect(dest)
        flash("账号或密码错误", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            flash("用户名至少 3 位，密码至少 6 位", "error")
            return redirect(url_for("register"))
        try:
            get_db().execute(
                "INSERT INTO users(username,password_hash,role,contact,created_at) VALUES(?,?,?,?,?)",
                (
                    username,
                    generate_password_hash(password),
                    "user",
                    request.form.get("contact", ""),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            flash("用户名已存在", "error")
            return redirect(url_for("register"))
        flash("注册成功，请登录", "ok")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_home():
    db = get_db()
    stats = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "listings": db.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM listings WHERE status='pending'").fetchone()[0],
        "ads": db.execute("SELECT COUNT(*) FROM ads").fetchone()[0],
    }
    pending = db.execute(
        "SELECT * FROM listings WHERE status='pending' ORDER BY id DESC LIMIT 20"
    ).fetchall()
    return render_template("admin/index.html", stats=stats, pending=pending)


@app.route("/admin/listings")
@admin_required
def admin_listings():
    status = request.args.get("status", "all")
    db = get_db()
    if status == "all":
        rows = db.execute(
            """SELECT l.*, c.name AS cat_name FROM listings l
               LEFT JOIN categories c ON c.id=l.category_id ORDER BY l.id DESC"""
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT l.*, c.name AS cat_name FROM listings l
               LEFT JOIN categories c ON c.id=l.category_id WHERE l.status=? ORDER BY l.id DESC""",
            (status,),
        ).fetchall()
    return render_template("admin/listings.html", rows=rows, status=status)


@app.route("/admin/listings/<int:item_id>/<action>", methods=["POST"])
@admin_required
def admin_listing_action(item_id, action):
    db = get_db()
    if action == "approve":
        db.execute("UPDATE listings SET status='approved' WHERE id=?", (item_id,))
    elif action == "reject":
        db.execute("UPDATE listings SET status='rejected' WHERE id=?", (item_id,))
    elif action == "feature":
        db.execute("UPDATE listings SET featured=1 WHERE id=?", (item_id,))
    elif action == "unfeature":
        db.execute("UPDATE listings SET featured=0 WHERE id=?", (item_id,))
    elif action == "delete":
        db.execute("DELETE FROM listings WHERE id=?", (item_id,))
    db.commit()
    return redirect(request.referrer or url_for("admin_listings"))


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO categories(parent_id,name,slug,intro,sort_order) VALUES(?,?,?,?,?)",
            (
                request.form.get("parent_id") or None,
                request.form["name"],
                request.form["slug"],
                request.form.get("intro", ""),
                int(request.form.get("sort_order") or 0),
            ),
        )
        db.commit()
        flash("分类已添加", "ok")
        return redirect(url_for("admin_categories"))
    rows = db.execute("SELECT * FROM categories ORDER BY parent_id IS NOT NULL, sort_order").fetchall()
    parents = db.execute("SELECT * FROM categories WHERE parent_id IS NULL").fetchall()
    return render_template("admin/categories.html", rows=rows, parents=parents)


@app.route("/admin/categories/<int:cid>/delete", methods=["POST"])
@admin_required
def admin_cat_delete(cid):
    get_db().execute("DELETE FROM categories WHERE id=?", (cid,))
    get_db().commit()
    return redirect(url_for("admin_categories"))


@app.route("/admin/ads", methods=["GET", "POST"])
@admin_required
def admin_ads():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO ads(title,image_url,link_url,position,active,sort_order) VALUES(?,?,?,?,?,?)",
            (
                request.form["title"],
                request.form["image_url"],
                request.form.get("link_url") or "#",
                request.form.get("position") or "home_banner",
                1 if request.form.get("active") else 0,
                int(request.form.get("sort_order") or 0),
            ),
        )
        db.commit()
        flash("广告已添加", "ok")
        return redirect(url_for("admin_ads"))
    rows = db.execute("SELECT * FROM ads ORDER BY position, sort_order").fetchall()
    return render_template("admin/ads.html", rows=rows)


@app.route("/admin/ads/<int:aid>/toggle", methods=["POST"])
@admin_required
def admin_ad_toggle(aid):
    db = get_db()
    row = db.execute("SELECT active FROM ads WHERE id=?", (aid,)).fetchone()
    if row:
        db.execute("UPDATE ads SET active=? WHERE id=?", (0 if row["active"] else 1, aid))
        db.commit()
    return redirect(url_for("admin_ads"))


@app.route("/admin/ads/<int:aid>/delete", methods=["POST"])
@admin_required
def admin_ad_delete(aid):
    get_db().execute("DELETE FROM ads WHERE id=?", (aid,))
    get_db().commit()
    return redirect(url_for("admin_ads"))


@app.route("/admin/notices", methods=["GET", "POST"])
@admin_required
def admin_notices():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO notices(title,body,active,created_at) VALUES(?,?,?,?)",
            (
                request.form["title"],
                request.form["body"],
                1,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        return redirect(url_for("admin_notices"))
    rows = db.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
    return render_template("admin/notices.html", rows=rows)


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    db = get_db()
    if request.method == "POST":
        for key in ("site_name", "site_tagline"):
            db.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, request.form.get(key, "")),
            )
        db.commit()
        flash("已保存", "ok")
        return redirect(url_for("admin_settings"))
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM settings")}
    return render_template("admin/settings.html", s=settings)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
else:
    if not os.path.exists(DB_PATH):
        init_db()
