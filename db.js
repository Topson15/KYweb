const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DATA_DIR = path.join(__dirname, "data");
const DB_FILE = path.join(DATA_DIR, "db.json");

function hashPassword(password, salt) {
  const usedSalt = salt || crypto.randomBytes(16).toString("hex");
  const hash = crypto.scryptSync(password, usedSalt, 32).toString("hex");
  return { salt: usedSalt, hash };
}

function verifyPassword(password, salt, hash) {
  const next = crypto.scryptSync(password, salt, 32).toString("hex");
  return crypto.timingSafeEqual(Buffer.from(hash, "hex"), Buffer.from(next, "hex"));
}

function seed() {
  const pass = hashPassword("navbox888");
  return {
    settings: {
      name: "NAVBOX",
      slogan: "站点合集导航系统 · 后台改内容，前台按权重排序",
      home: "navbox.example",
      noticeDate: "2026-09-03",
      noticeHtml: "收录站点仅作导航索引；访问前请自行甄别风险。"
    },
    admin: { username: "admin", salt: pass.salt, hash: pass.hash },
    tabs: ["常规入口", "工具站", "社区站", "独立站", "国外站", "资料站", "评测站"],
    tags: ["效率工具", "设计资源", "开发文档", "AI 应用", "学习笔记", "开源项目", "资讯媒体", "云存储", "API 目录", "图标素材"],
    sites: [
      { id: "mdn", name: "MDN Web Docs", url: "https://developer.mozilla.org", tab: "资料站", tags: ["开发文档"], desc: "前端与 Web API 权威文档。", badge: "热门", weight: 100, status: "on" },
      { id: "github", name: "GitHub", url: "https://github.com", tab: "工具站", tags: ["开源项目", "开发文档"], desc: "代码托管与开源协作。", badge: "热门", weight: 95, status: "on" },
      { id: "figma", name: "Figma", url: "https://www.figma.com", tab: "工具站", tags: ["设计资源"], desc: "协作式界面设计工具。", badge: "推荐", weight: 80, status: "on" },
      { id: "hf", name: "Hugging Face", url: "https://huggingface.co", tab: "工具站", tags: ["AI 应用", "开源项目"], desc: "模型、数据集与 AI 应用中心。", badge: "热门", weight: 88, status: "on" },
      { id: "notion", name: "Notion", url: "https://www.notion.so", tab: "独立站", tags: ["效率工具", "学习笔记"], desc: "笔记、知识库与团队文档。", badge: "新", weight: 70, status: "on" },
      { id: "devdocs", name: "DevDocs", url: "https://devdocs.io", tab: "资料站", tags: ["开发文档"], desc: "多语言 API 文档聚合。", badge: "", weight: 60, status: "on" },
      { id: "chatgpt", name: "ChatGPT", url: "https://chatgpt.com", tab: "工具站", tags: ["AI 应用", "效率工具"], desc: "通用对话与写作助手。", badge: "热门", weight: 90, status: "on" },
      { id: "caniuse", name: "Can I Use", url: "https://caniuse.com", tab: "资料站", tags: ["开发文档"], desc: "浏览器特性兼容性查询。", badge: "", weight: 55, status: "on" }
    ],
    featured: [
      { id: "f1", title: "示例供应 · 图标包", cat: "设计资源", until: "2027-06-09", contact: "@design_demo", desc: "可替换为你的置顶供应信息。", time: "2026-09-03 00:00", weight: 100, status: "on" },
      { id: "f2", title: "示例供应 · 文档镜像", cat: "开发文档", until: "2027-05-10", contact: "@docs_demo", desc: "适合放长期合作或公共服务。", time: "2026-09-03 01:00", weight: 80, status: "on" }
    ],
    expose: [
      { id: "e1", when: "2026-09-01", title: "示例：失效域名提醒", level: "提示", body: "把已确认失效的站点写在这里。", weight: 100, status: "on" },
      { id: "e2", when: "2026-08-20", title: "示例：冒名镜像", level: "归档", body: "只记录可核验事实。", weight: 70, status: "on" }
    ],
    tools: [
      { id: "t1", name: "主题切换", desc: "前台右上角可切换晨光白 / 暗夜黑。", href: "/", weight: 50, status: "on" },
      { id: "t2", name: "后台权重", desc: "数字越大，前台排得越靠前。", href: "/admin", weight: 90, status: "on" }
    ],
    notice: [
      { title: "1. 合集说明", body: "前台按权重从高到低展示已上架内容。", hint: "在后台改权重后刷新前台即可。" },
      { title: "2. 账号", body: "默认账号 admin，初始密码 navbox888，登录后请立刻修改。", hint: "不要把后台地址发给普通人。" }
    ]
  };
}

function load() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(DB_FILE)) {
    const fresh = seed();
    fs.writeFileSync(DB_FILE, JSON.stringify(fresh, null, 2));
    return fresh;
  }
  return JSON.parse(fs.readFileSync(DB_FILE, "utf8"));
}

function save(db) {
  const tmp = DB_FILE + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(db, null, 2));
  fs.renameSync(tmp, DB_FILE);
}

function nid(prefix) {
  return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

function sortByWeight(list) {
  return (list || []).slice().sort((a, b) => (b.weight || 0) - (a.weight || 0));
}

module.exports = { load, save, seed, hashPassword, verifyPassword, nid, sortByWeight, DB_FILE };
