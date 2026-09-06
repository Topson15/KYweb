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
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
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
        ("tools", "常规接口", "api", "开放 API、Webhook、SDK 与文档索引。适合对接内部系统和第三方服务。", 1),
        ("tools", "独立站", "indie", "独立开发者产品与小而美站点，强调可自托管、可试用。", 2),
        ("tools", "设计资源", "design", "图标、字体、组件库、设计系统与落地页模板。", 3),
        ("tools", "开发框架", "framework", "前后端框架、脚手架与部署模板。", 4),
        ("tools", "数据服务", "data", "公开数据集、报表面板与埋点方案。", 5),
        ("tools", "协作办公", "collab", "文档、任务、会议纪要与知识库工具。", 6),
        ("tools", "安全合规", "secure", "备份、权限、审计与基础安全检测。", 7),
        ("demand", "供应", "supply", "可提供的产品、服务、设计或开发产能。", 1),
        ("demand", "求购", "buy", "写清预算、交付物和截止时间的采购信息。", 2),
        ("demand", "合作", "coop", "联合运营、渠道分发与技术合作。", 3),
        ("demand", "外包项目", "outsource", "短期项目制需求，适合个人开发者与工作室。", 4),
        ("reports", "虚假宣传", "fake", "夸大承诺、无法兑现的案例摘要，仅供参考。", 1),
        ("reports", "服务纠纷", "dispute", "履约争议与售后问题公开记录。", 2),
        ("reports", "跑路预警", "alert", "失联、拒不交付等风险提示，需人工复核。", 3),
        ("utils", "格式转换", "convert", "文档、图片、字幕等格式转换入口。", 1),
        ("utils", "站点检测", "check", "可用性、证书与基础安全检测。", 2),
        ("utils", "文案模板", "tpl", "需求说明书、报价单、验收单模板。", 3),
        ("utils", "计算小工具", "calc", "工期、报价系数与订阅成本估算。", 4),
    ]
    for parent_slug, name, slug, intro, order in children:
        db.execute(
            "INSERT INTO categories(parent_id,name,slug,intro,sort_order) VALUES(?,?,?,?,?)",
            (parent_ids[parent_slug], name, slug, intro, order),
        )
    cat = {r["slug"]: r["id"] for r in db.execute("SELECT id,slug FROM categories")}
    expire = (datetime.utcnow() + timedelta(days=180)).date().isoformat()
    listings = [
        ("巡航看板 · 数据监控套件", cat["api"], "supply", "运营向实时看板，支持多数据源与周报。", "指标订阅、异常告警、权限分组。提供 14 天试用。", "@ops_demo", "https://example.com/dashboard", 1),
        ("开放 Webhook 网关", cat["api"], "supply", "把内部事件转成标准 Webhook，带重试与签名。", "适合把旧系统接到飞书/钉钉/自建机器人。", "@hook_lab", "https://example.com/hook", 1),
        ("发票识别 API", cat["api"], "supply", "增值税发票字段抽取，按次计费。", "支持 PDF/图片，回传 JSON，可私有化。", "@ocr_plus", "https://example.com/ocr", 0),
        ("独立文档站生成器", cat["indie"], "supply", "把 Markdown 仓库变成带搜索的文档站。", "一键部署，支持版本切换与暗色主题。", "@docsmini", "https://example.com/docs", 1),
        ("轻量预约页", cat["indie"], "supply", "给线下服务用的档期预约页，免登录。", "可导出日历，适合工作室与培训。", "@bookly", "https://example.com/book", 0),
        ("个人作品集模板", cat["indie"], "supply", "设计师/开发者作品集，含案例页。", "静态导出，可挂自己的域名。", "@folio", "https://example.com/folio", 0),
        ("图标与插画包 2026", cat["design"], "supply", "1200+ 线性图标，商用授权清晰。", "含 Figma 组件与 SVG 压缩包。", "@iconset", "https://example.com/icons", 1),
        ("落地页组件库", cat["design"], "supply", "营销页模块：价格表、FAQ、对比表。", "适配主流前端框架，给源文件。", "@landkit", "https://example.com/land", 0),
        ("中文字体搭配手册", cat["design"], "supply", "标题/正文配对示例与授权说明。", "在线预览，可下载对照表。", "@typecn", "https://example.com/type", 0),
        ("Flask 后台脚手架", cat["framework"], "supply", "带登录、权限、CSV 导出的后台起点。", "MIT 协议，文档里有部署清单。", "@flaskkit", "https://example.com/flask", 1),
        ("前端单体模板", cat["framework"], "supply", "列表+详情+筛选的管理台界面。", "只含静态页，方便接自己的 API。", "@adminui", "https://example.com/ui", 0),
        ("公开行业数据集", cat["data"], "supply", "零售/招聘/物流脱敏样本，按月更新。", "CSV/Parquet，附字段字典。", "@opendata", "https://example.com/data", 1),
        ("埋点方案白皮书", cat["data"], "supply", "事件命名规范与看板指标模板。", "适合 10 人以下产品团队。", "@trackspec", "https://example.com/track", 0),
        ("团队知识库托管", cat["collab"], "supply", "私有化 Wiki，Markdown + 权限分级。", "支持全文检索与页面锁。", "@wikibox", "https://example.com/wiki", 1),
        ("会议纪要助手", cat["collab"], "supply", "录音转文字并生成待办。", "仅作演示，不存储敏感音频。", "@meetnote", "https://example.com/meet", 0),
        ("自动备份盒子", cat["secure"], "supply", "把站点文件和数据库定时打包装云盘。", "保留 30 天版本，失败发邮件。", "@bakbox", "https://example.com/bak", 1),
        ("权限体检清单", cat["secure"], "supply", "检查后台账号、弱口令与过期密钥。", "输出 PDF 报告，给运维签字。", "@aclcheck", "https://example.com/acl", 0),
        ("品牌官网改版供应", cat["supply"], "supply", "承接企业官网改版，含移动端。", "周期 3–6 周，提供信息架构稿。", "@studio_a", "https://example.com/studio", 1),
        ("小程序页面开发档期", cat["supply"], "supply", "本月仍有 2 个档期，按页报价。", "不接金融与博彩类目。", "@mini_dev", "https://example.com/mini", 0),
        ("求购：可私有化知识库", cat["buy"], "demand", "20 人团队，要权限和全文检索。", "预算面议，需提供演示环境。", "@buyer01", "", 1),
        ("求购：数据看板外包", cat["buy"], "demand", "对接现有订单库，要周报邮件。", "希望 4 周内上线第一版。", "@buyer02", "", 0),
        ("求购：设计系统整理", cat["buy"], "demand", "把散落组件收成 Figma 库。", "有现成页面可参考，要文档。", "@buyer03", "", 0),
        ("渠道互推合作", cat["coop"], "coop", "工具类站点互换友情链接与联合活动。", "需提供真实 UV 区间，不买量。", "@partner01", "https://example.com/partner", 1),
        ("内容共创计划", cat["coop"], "coop", "寻找垂直领域作者写评测。", "按篇结算，先看过往样本。", "@editor01", "", 0),
        ("外包：报名页 3 天交付", cat["outsource"], "demand", "活动报名+审核名单导出。", "提供设计稿，不要后台太复杂。", "@event01", "", 0),
        ("外包：旧站迁移备案", cat["outsource"], "demand", "静态站迁到新域名并保留链接。", "要 301 清单和验收表。", "@migrate01", "", 0),
        ("某平台承诺「稳赚」未兑现", cat["fake"], "report", "宣传保本，实际无法提现。摘要存档。", "请自行核验，本站不构成指控。保留对话截图再投诉。", "@editor", "", 0),
        ("改版项目拖期两个月", cat["dispute"], "report", "验收标准争议，双方各执一词。", "建议合同写清里程碑付款。", "@editor", "", 0),
        ("供应商失联预警（演示）", cat["alert"], "report", "约定交付日后连续失联。", "演示数据。真实预警需后台复核。", "@editor", "", 0),
        ("Markdown ↔ Word 转换", cat["convert"], "supply", "保留标题层级和表格。", "浏览器内转换，文件不上传服务器。", "@cvt01", "https://example.com/md", 0),
        ("图片批量压缩", cat["convert"], "supply", "按目标体积压缩 JPG/PNG。", "适合落地页配图。", "@cvt02", "https://example.com/img", 0),
        ("证书与 HTTPS 检测", cat["check"], "supply", "查过期时间和跳转是否正确。", "输出简单报告，可定期扫。", "@chk01", "https://example.com/ssl", 0),
        ("死链抽查", cat["check"], "supply", "按站点地图抽查 200 个链接。", "适合改版后验收。", "@chk02", "https://example.com/link", 0),
        ("需求说明书模板", cat["tpl"], "supply", "含范围、验收、不做什么。", "可直接改成自己的项目。", "@tpl01", "", 1),
        ("验收单模板", cat["tpl"], "supply", "功能点打勾 + 签字栏。", "减少口头验收纠纷。", "@tpl02", "", 0),
        ("工期估算表", cat["calc"], "supply", "按页面数和接口数估人天。", "仅供参考，复杂需求另算。", "@calc01", "", 0),
        ("订阅成本对照", cat["calc"], "supply", "把年付/月付工具摊到人月。", "适合小团队做工具盘点。", "@calc02", "", 0),
    ]
    for t, cid, kind, summary, body, contact, site, feat in listings:
        db.execute(
            """INSERT INTO listings(title,category_id,kind,summary,body,contact,website,logo,status,featured,expire_at,author_id,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t, cid, kind, summary, body, contact, site, "", "approved", feat, expire, 2, now),
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
    db.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("site_name", "看见收录"))
    db.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("site_tagline", "工具 · 供需 · 模板 · 人工审核"))
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


def listing_query(db, extra="", args=(), limit=12):
    sql = f"""SELECT l.*, c.name AS cat_name, c.slug AS cat_slug FROM listings l
              LEFT JOIN categories c ON c.id=l.category_id
              WHERE l.status='approved' {extra}
              ORDER BY l.featured DESC, l.id DESC LIMIT {int(limit)}"""
    return db.execute(sql, args).fetchall()


@app.route("/")
def index():
    db = get_db()
    banners = db.execute(
        "SELECT * FROM ads WHERE position='home_banner' AND active=1 ORDER BY sort_order"
    ).fetchall()
    featured = listing_query(db, "AND l.featured=1", limit=8)
    latest = listing_query(db, limit=10)
    supplies = listing_query(db, "AND l.kind='supply'", limit=8)
    demands = listing_query(db, "AND l.kind IN ('demand','coop')", limit=8)
    reports = listing_query(db, "AND l.kind='report'", limit=6)
    tools_parent = db.execute("SELECT * FROM categories WHERE slug='tools'").fetchone()
    tool_cats, tool_listings, current = [], [], None
    if tools_parent:
        tool_cats = db.execute(
            "SELECT * FROM categories WHERE parent_id=? ORDER BY sort_order",
            (tools_parent["id"],),
        ).fetchall()
        current_slug = request.args.get("cat") or (tool_cats[0]["slug"] if tool_cats else None)
        current = next((c for c in tool_cats if c["slug"] == current_slug), tool_cats[0] if tool_cats else None)
        if current:
            tool_listings = listing_query(
                db,
                "AND (l.category_id=? OR c.parent_id=?)",
                (current["id"], current["id"]),
                20,
            )
    counts = {
        "all": db.execute("SELECT COUNT(*) FROM listings WHERE status='approved'").fetchone()[0],
        "cats": db.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM listings WHERE status='pending'").fetchone()[0],
    }
    notice = db.execute("SELECT * FROM notices WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    return render_template(
        "index.html",
        banners=banners,
        featured=featured,
        latest=latest,
        supplies=supplies,
        demands=demands,
        reports=reports,
        tool_cats=tool_cats,
        tool_listings=tool_listings,
        current_cat=current,
        notice=notice,
        tools_parent=tools_parent,
        counts=counts,
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
    related = []
    if item["category_id"]:
        related = db.execute(
            """SELECT l.*, c.name AS cat_name, c.slug AS cat_slug FROM listings l
               LEFT JOIN categories c ON c.id=l.category_id
               WHERE l.status='approved' AND l.category_id=? AND l.id!=?
               ORDER BY l.id DESC LIMIT 4""",
            (item["category_id"], item["id"]),
        ).fetchall()
    return render_template("detail.html", item=item, related=related)


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


@app.route("/admin/reload-demo", methods=["POST"])
@admin_required
def admin_reload_demo():
    """清空业务数据并重新写入加厚演示内容。账号保留。"""
    db = get_db()
    db.execute("DELETE FROM listings")
    db.execute("DELETE FROM ads")
    db.execute("DELETE FROM notices")
    db.execute("DELETE FROM categories")
    db.execute("DELETE FROM settings")
    db.commit()
    db.close()
    g.pop("db", None)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    seed(raw)
    raw.commit()
    raw.close()
    flash("演示内容已重新载入，请刷新前台", "ok")
    return redirect(url_for("admin_home"))


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
