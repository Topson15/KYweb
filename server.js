const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { URL } = require("url");
const dbx = require("./db");

const PORT = process.env.PORT || 3000;
const PUBLIC = path.join(__dirname, "public");
const sessions = new Map();

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon"
};

function send(res, code, body, headers) {
  const extra = headers || {};
  extra["Access-Control-Allow-Credentials"] = "true";
  res.writeHead(code, extra);
  res.end(body);
}

function json(res, code, obj, cookie) {
  const headers = { "Content-Type": "application/json; charset=utf-8" };
  if (cookie) headers["Set-Cookie"] = cookie;
  send(res, code, JSON.stringify(obj), headers);
}

function parseCookies(req) {
  const out = {};
  String(req.headers.cookie || "").split(";").forEach((part) => {
    const i = part.indexOf("=");
    if (i > -1) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  });
  return out;
}

function adminUser(req) {
  const sid = parseCookies(req).sid;
  const s = sid && sessions.get(sid);
  if (!s || s.exp < Date.now()) return null;
  return s.user;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); }
      catch (e) {
        const params = new URLSearchParams(raw);
        const obj = {};
        params.forEach((v, k) => { obj[k] = v; });
        resolve(obj);
      }
    });
    req.on("error", reject);
  });
}

function publicSite(s) {
  return {
    id: s.id, name: s.name, url: s.url, tab: s.tab, tags: s.tags || [],
    desc: s.desc, badge: s.badge || "", weight: s.weight || 0
  };
}

function normalizeTags(tags) {
  if (Array.isArray(tags)) return tags;
  return String(tags || "").split(/[,，]/).map((s) => s.trim()).filter(Boolean);
}

function upsert(db, key, body, fields) {
  const item = { id: body.id || dbx.nid(key[0]), status: body.status || "on" };
  fields.forEach((f) => { item[f] = body[f]; });
  item.weight = Number(body.weight || 0);
  if (Object.prototype.hasOwnProperty.call(item, "tags")) item.tags = normalizeTags(item.tags);
  const list = db[key] || [];
  const idx = list.findIndex((x) => x.id === item.id);
  if (idx >= 0) list[idx] = { ...list[idx], ...item };
  else list.push(item);
  db[key] = list;
  dbx.save(db);
  return item;
}

async function handleApi(req, res, url) {
  const p = url.pathname;
  const method = req.method;

  if (p === "/api/public" && method === "GET") {
    const db = dbx.load();
    return json(res, 200, {
      ok: true,
      settings: db.settings,
      tabs: db.tabs,
      tags: db.tags,
      notice: db.notice,
      sites: dbx.sortByWeight((db.sites || []).filter((s) => s.status !== "off")).map(publicSite),
      featured: dbx.sortByWeight((db.featured || []).filter((s) => s.status !== "off")),
      expose: dbx.sortByWeight((db.expose || []).filter((s) => s.status !== "off")),
      tools: dbx.sortByWeight((db.tools || []).filter((s) => s.status !== "off"))
    });
  }

  if (p === "/api/login" && method === "POST") {
    const body = await readBody(req);
    const db = dbx.load();
    const username = String(body.username || "").trim();
    const password = String(body.password || "");
    if (username !== db.admin.username || !dbx.verifyPassword(password, db.admin.salt, db.admin.hash)) {
      return json(res, 400, { ok: false, error: "账号或密码不对" });
    }
    const sid = crypto.randomBytes(16).toString("hex");
    sessions.set(sid, { user: username, exp: Date.now() + 7 * 24 * 3600 * 1000 });
    return json(res, 200, { ok: true, username }, "sid=" + sid + "; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800");
  }

  if (p === "/api/logout" && method === "POST") {
    const sid = parseCookies(req).sid;
    if (sid) sessions.delete(sid);
    return json(res, 200, { ok: true }, "sid=; Path=/; Max-Age=0");
  }

  if (p === "/api/me" && method === "GET") {
    return json(res, 200, { ok: true, admin: adminUser(req) });
  }

  if (!adminUser(req) && p.startsWith("/api/admin")) {
    return json(res, 401, { ok: false, error: "请先登录后台" });
  }

  if (p === "/api/admin/all" && method === "GET") {
    const db = dbx.load();
    return json(res, 200, {
      ok: true,
      settings: db.settings,
      tabs: db.tabs,
      tags: db.tags,
      sites: dbx.sortByWeight(db.sites),
      featured: dbx.sortByWeight(db.featured),
      expose: dbx.sortByWeight(db.expose),
      tools: dbx.sortByWeight(db.tools),
      notice: db.notice,
      adminUser: db.admin.username
    });
  }

  const maps = {
    "/api/admin/sites": ["sites", ["name", "url", "tab", "tags", "desc", "badge", "status"]],
    "/api/admin/featured": ["featured", ["title", "cat", "until", "contact", "desc", "time", "status"]],
    "/api/admin/expose": ["expose", ["when", "title", "level", "body", "status"]],
    "/api/admin/tools": ["tools", ["name", "desc", "href", "status"]]
  };

  if (maps[p] && method === "POST") {
    const body = await readBody(req);
    const item = upsert(dbx.load(), maps[p][0], body, maps[p][1]);
    return json(res, 200, { ok: true, item });
  }

  const del = p.match(/^\/api\/admin\/(sites|featured|expose|tools)\/([^/]+)$/);
  if (del && method === "DELETE") {
    const db = dbx.load();
    db[del[1]] = (db[del[1]] || []).filter((x) => x.id !== decodeURIComponent(del[2]));
    dbx.save(db);
    return json(res, 200, { ok: true });
  }

  if (p === "/api/admin/weight" && method === "PUT") {
    const body = await readBody(req);
    const db = dbx.load();
    if (!db[body.key]) return json(res, 400, { ok: false, error: "类型不对" });
    const item = db[body.key].find((x) => x.id === body.id);
    if (!item) return json(res, 404, { ok: false, error: "没找到" });
    item.weight = Number(body.weight || 0);
    dbx.save(db);
    return json(res, 200, { ok: true, item });
  }

  if (p === "/api/admin/settings" && method === "PUT") {
    const body = await readBody(req);
    const db = dbx.load();
    db.settings = { ...db.settings, ...(body.settings || {}) };
    if (Array.isArray(body.tabs)) db.tabs = body.tabs.filter(Boolean);
    if (Array.isArray(body.tags)) db.tags = body.tags.filter(Boolean);
    if (Array.isArray(body.notice)) db.notice = body.notice;
    dbx.save(db);
    return json(res, 200, { ok: true });
  }

  if (p === "/api/admin/password" && method === "PUT") {
    const body = await readBody(req);
    const password = String(body.password || "");
    if (password.length < 6) return json(res, 400, { ok: false, error: "密码至少 6 位" });
    const db = dbx.load();
    const next = dbx.hashPassword(password);
    db.admin.salt = next.salt;
    db.admin.hash = next.hash;
    if (body.username) db.admin.username = String(body.username).trim();
    dbx.save(db);
    return json(res, 200, { ok: true });
  }

  if (p === "/api/admin/export" && method === "GET") {
    const db = dbx.load();
    return send(res, 200, JSON.stringify(db, null, 2), {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": "attachment; filename=navbox-backup.json"
    });
  }

  if (p === "/api/admin/import" && method === "POST") {
    const body = await readBody(req);
    if (!body || !body.sites) return json(res, 400, { ok: false, error: "备份文件不对" });
    dbx.save(body);
    return json(res, 200, { ok: true });
  }

  return json(res, 404, { ok: false, error: "接口不存在" });
}

function safeFile(rel) {
  const clean = path.normalize(rel).replace(/^(\.\.[/\\])+/, "");
  const full = path.join(PUBLIC, clean);
  if (!full.startsWith(PUBLIC)) return null;
  return full;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://localhost");
    if (url.pathname.startsWith("/api/")) return handleApi(req, res, url);

    let rel = url.pathname === "/" ? "/index.html" : url.pathname;
    if (rel === "/admin" || rel === "/admin/") rel = "/admin.html";
    const file = safeFile(rel);
    if (file && fs.existsSync(file) && fs.statSync(file).isFile()) {
      const ext = path.extname(file);
      return send(res, 200, fs.readFileSync(file), { "Content-Type": MIME[ext] || "application/octet-stream" });
    }
    send(res, 404, "Not Found", { "Content-Type": "text/plain; charset=utf-8" });
  } catch (err) {
    console.error(err);
    json(res, 500, { ok: false, error: "服务器错误" });
  }
});

server.listen(PORT, "0.0.0.0", () => {
  dbx.load();
  console.log("NAVBOX 系统已启动 http://localhost:" + PORT);
  console.log("前台 /    后台 /admin    默认 admin / navbox888");
});
