(function () {
  const THEME_KEY = "navbox-theme";
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
    const btn = document.getElementById("themeBtn");
    if (btn) btn.textContent = theme === "dark" ? "暗夜黑 ▾" : "晨光白 ▾";
  }
  window.toggleTheme = function () {
    applyTheme((localStorage.getItem(THEME_KEY) || "light") === "dark" ? "light" : "dark");
  };
  window.copyText = function (t) {
    navigator.clipboard.writeText(t).then(function () { alert("已复制：" + t); });
  };

  function sortHint(n) { return n || 0; }

  function headerHTML(data, page) {
    const s = data.settings;
    const pills = [
      { id: "sites", label: "精选合集", href: "/" },
      { id: "supply", label: "供需广场", href: "/supply.html" },
      { id: "expose", label: "曝光台", href: "/expose.html" },
      { id: "tools", label: "实用工具", href: "/tools.html" }
    ].map(function (n) {
      return '<a class="pill' + (n.id === page ? " active" : "") + '" href="' + n.href + '">' + n.label + "</a>";
    }).join("");
    return (
      '<header class="topbar">' +
        '<div class="brand"><div class="logo">🧭</div><div>' +
        "<h1>" + s.name + "</h1><p>" + s.slogan + "</p>" +
        '<div class="addr">唯一入口 <code>' + s.home + '</code> <button class="copy" type="button" onclick="copyText(\'' + s.home + "')\">复制</button></div>" +
        "</div></div>" +
        "<div><nav class=\"navpills\">" + pills + "</nav>" +
        '<div class="mid-contacts" style="margin-top:10px">' +
        '<a class="mini-card" href="/submit.html">客服入口<b>在线咨询</b></a>' +
        '<a class="mini-card" href="/admin">管理后台<b>改内容/权重</b></a></div></div>' +
        '<div class="right-tools"><div class="tool-row">' +
        '<button class="ghost" id="themeBtn" type="button" onclick="toggleTheme()">晨光白 ▾</button>' +
        '<a class="outline" href="/submit.html">申请收录</a>' +
        '<a class="solid" href="/admin">后台</a></div>' +
        '<div class="draw-box"><div class="draw-item">已上架站点 ' + String(data.sites.length).padStart(3, "0") +
        '<div class="balls"><span class="ball g">12</span><span class="ball b">18</span><span class="ball r">07</span><span class="ball k">23</span></div></div>' +
        '<div class="draw-item">权重优先排序<div class="balls"><span class="ball r">10</span><span class="ball b">08</span><span class="ball g">06</span><span class="ball k">04</span></div></div></div>' +
        "</div></header>"
    );
  }

  function siteCard(s) {
    const badge = s.badge ? '<span class="badge ' + (s.badge === "热门" ? "hot" : s.badge === "新" ? "new" : "") + '">' + s.badge + "</span>" : "";
    return '<article class="scard"><div class="scard-top"><h3>' + s.name + "</h3>" + badge + "</div>" +
      '<div class="url">' + String(s.url || "").replace(/^https?:\/\//, "") + "</div><p>" + s.desc + "</p>" +
      '<div class="scard-ft"><span class="badge">权重 ' + sortHint(s.weight) + " · " + s.tab + "</span>" +
      '<span style="display:flex;gap:6px"><a class="go" href="/site.html?id=' + encodeURIComponent(s.id) + '">详情</a>' +
      '<a class="go" href="' + s.url + '" target="_blank" rel="noopener noreferrer">访问</a></span></div></article>';
  }

  function featuredCard(item) {
    return '<article class="fcard"><div class="fcard-hd"><div class="thumb">📦</div><div style="flex:1"><h3>' + item.title + "</h3>" +
      '<div class="meta">分类：' + item.cat + "　有效期至：" + item.until + "<br/>联系：" + item.contact + "</div></div>" +
      '<span class="tag-supply">供应</span></div><p>' + item.desc + "</p><div class=\"more\">权重 " + sortHint(item.weight) + "</div><time>🕒 " + (item.time || "") + "</time></article>";
  }

  window.closeModal = function () {
    const el = document.getElementById("overlay");
    if (el) el.classList.remove("show");
  };

  async function boot() {
    applyTheme(localStorage.getItem(THEME_KEY) || "light");
    const page = document.body.getAttribute("data-page") || "sites";
    const res = await fetch("/api/public");
    const data = await res.json();
    const root = document.getElementById("app");
    root.insertAdjacentHTML("afterbegin", headerHTML(data, page));
    root.insertAdjacentHTML("beforeend", '<footer class="footer">' + data.settings.name + " · 前台按权重从高到低排列 · <a href=\"/admin\">进入后台</a></footer>" +
      '<div class="overlay" id="overlay" onclick="if(event.target===this) closeModal()"><div class="modal" id="modal"></div></div>');
    const mount = document.getElementById("page");
    const params = new URLSearchParams(location.search);
    const tab = params.get("tab") || "常规入口";
    const tag = params.get("tag") || "";
    const q = (params.get("q") || "").trim().toLowerCase();

    if (page === "sites") {
      const tabs = (data.tabs || []).map(function (t) {
        return '<a class="tab' + (tab === t ? " active" : "") + '" href="/?tab=' + encodeURIComponent(t) + (tag ? "&tag=" + encodeURIComponent(tag) : "") + '">' + t + "</a>";
      }).join("");
      const chips = (data.tags || []).map(function (t) {
        return '<a class="chip' + (tag === t ? " active" : "") + '" href="/?tab=' + encodeURIComponent(tab) + (tag === t ? "" : "&tag=" + encodeURIComponent(t)) + '">' + t + "</a>";
      }).join("");
      const list = data.sites.filter(function (s) {
        return (tab === "常规入口" || s.tab === tab) && (!tag || (s.tags || []).indexOf(tag) !== -1) &&
          (!q || [s.name, s.url, s.desc, s.tab].join(" ").toLowerCase().indexOf(q) !== -1);
      });
      mount.innerHTML = '<section class="panel"><div class="banners">' +
        '<a class="banner b1" href="/submit.html"><div>BANNER A<small>后台可改站点，这里先留广告位</small></div></a>' +
        '<a class="banner b2" href="/supply.html"><div>BANNER B<small>供需内容在后台「供应」里改</small></div></a>' +
        '<a class="banner b3" href="/tools.html"><div>BANNER C<small>工具页同样走权重</small></div></a>' +
        '<a class="banner b4" href="/admin"><div>BANNER D<small>点这里进入后台</small></div></a></div>' +
        '<p class="note">' + (data.settings.noticeHtml || "") + "</p>" +
        '<div class="featured">' + data.featured.map(featuredCard).join("") + "</div></section>" +
        '<section class="panel"><div class="sec-hd"><h2>精选合集</h2><div class="sec-actions"><a class="ghost" href="/submit.html">申请收录</a><a class="ghost" href="/search.html">搜索</a></div></div>' +
        '<div class="warn">' + (data.settings.noticeHtml || "") + "</div>" +
        '<div class="tabs">' + tabs + '</div><div class="chips">' + chips + "</div>" +
        '<div class="grid">' + (list.length ? list.map(siteCard).join("") : '<div class="empty">暂无站点，请到后台添加。</div>') + "</div></section>";
      if (!localStorage.getItem("navbox-notice-seen") && data.notice) {
        document.getElementById("modal").innerHTML = "<h3>公告</h3>" + data.notice.map(function (n) {
          return '<div class="block"><h4>' + n.title + "</h4><p>" + n.body + '</p><div class="hint">' + n.hint + "</div></div>";
        }).join("") + '<div class="close-row"><button class="solid" type="button" onclick="localStorage.setItem(\'navbox-notice-seen\',\'1\');closeModal()">我已阅读</button></div>';
        document.getElementById("overlay").classList.add("show");
      }
    } else if (page === "supply") {
      mount.innerHTML = '<section class="panel"><div class="sec-hd"><h2>供需广场</h2></div><div class="featured">' + data.featured.map(featuredCard).join("") + "</div></section>";
    } else if (page === "expose") {
      mount.innerHTML = '<section class="panel"><h2 style="margin-bottom:12px">曝光台</h2><div class="timeline">' + data.expose.map(function (e) {
        return '<article class="titem"><div class="when">' + e.when + ' · <span class="badge">' + e.level + "</span> · 权重 " + sortHint(e.weight) + "</div><h3>" + e.title + "</h3><p style=\"margin-top:8px;color:var(--muted);line-height:1.7\">" + e.body + "</p></article>";
      }).join("") + "</div></section>";
    } else if (page === "tools") {
      mount.innerHTML = '<section class="panel"><h2 style="margin-bottom:12px">实用工具</h2><div class="tools-grid">' + data.tools.map(function (t) {
        return '<article class="tool-box"><h3>' + t.name + "</h3><p>" + t.desc + "</p><a class=\"go\" href=\"" + t.href + "\">打开</a></article>";
      }).join("") + "</div></section>";
    } else if (page === "site") {
      const s = data.sites.filter(function (x) { return x.id === params.get("id"); })[0];
      mount.innerHTML = s
        ? '<section class="panel"><div class="detail"><div><h2>' + s.name + "</h2><p class=\"note\">" + s.desc + "</p><div class=\"kv\"><div>分类：<b>" + s.tab + "</b></div><div>权重：<b>" + sortHint(s.weight) + "</b></div><div>地址：<b>" + s.url + "</b></div></div><div class=\"sec-actions\" style=\"margin-top:16px\"><a class=\"solid\" href=\"" + s.url + "\" target=\"_blank\" rel=\"noopener noreferrer\">打开站点</a><a class=\"ghost\" href=\"/\">返回</a></div></div><div class=\"tool-box\"><h3>排序说明</h3><p>权重越大，首页同分类里排得越靠前。到后台改数字即可。</p></div></div></section>"
        : '<section class="panel"><h2>未找到站点</h2></section>';
    } else if (page === "search") {
      const list = data.sites.filter(function (s) { return !q || [s.name, s.url, s.desc].join(" ").toLowerCase().indexOf(q) !== -1; });
      mount.innerHTML = '<section class="panel"><h2>搜索</h2><form class="searchbox" action="/search.html" method="get"><input name="q" value="' + q.replace(/"/g, "&quot;") + '" placeholder="名称或域名" /><button class="solid" type="submit">搜索</button></form><div class="grid" style="margin-top:16px">' + (list.length ? list.map(siteCard).join("") : '<div class="empty">没有结果</div>') + "</div></section>";
    } else if (page === "submit") {
      mount.innerHTML = '<section class="panel"><h2 style="margin-bottom:12px">申请收录</h2><p class="note">演示表单不会写入后台。正式使用可把提交接到邮箱或自己的接口。</p><form class="form" onsubmit="event.preventDefault();alert(\'已记录意向，请到后台手工录入。\');"><label>站点名称<input required></label><label>网址<input required></label><label>简介<textarea></textarea></label><button class="solid" type="submit">提交</button></form></section>';
    }
  }
  document.addEventListener("DOMContentLoaded", boot);
})();
