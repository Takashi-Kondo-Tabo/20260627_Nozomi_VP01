const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------- タブ切り替え ----------
$$(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".tab-btn").forEach(b => b.classList.remove("active"));
    $$(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

function showError(container, message) {
  container.innerHTML = `<div class="error-banner">${escapeHtml(message)}</div>`;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// ---------- ステータス ----------
async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const el = $("#status");
    if (!data.has_api_key) {
      el.textContent = "APIキー未設定";
      el.style.color = "#d1453b";
    } else if (!data.has_index) {
      el.textContent = "インデックス未構築";
    } else {
      el.textContent = `${data.total_articles} 件インデックス済み`;
    }

    $("#index-info").innerHTML = data.has_index
      ? `インデックス済み記事数: <strong>${data.total_articles}</strong> 件 ${data.has_style_guide ? " / 文体分析済み" : ""}`
      : "インデックスがまだ構築されていません。";
  } catch (e) {
    $("#status").textContent = "接続エラー";
  }
}

// ---------- ダッシュボード ----------
$("#btn-build-index").addEventListener("click", async () => {
  const btn = $("#btn-build-index");
  btn.disabled = true;
  btn.textContent = "構築中...";
  try {
    const res = await fetch("/api/index", { method: "POST" });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    alert(`インデックス構築完了: ${data.total} 件`);
    refreshStatus();
  } catch (e) {
    alert("エラー: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "インデックスを再構築";
  }
});

$("#btn-analyze-style").addEventListener("click", async () => {
  const btn = $("#btn-analyze-style");
  btn.disabled = true;
  btn.textContent = "分析中...";
  try {
    const res = await fetch("/api/analyze-style", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: true }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    $("#style-guide-card").style.display = "block";
    $("#style-guide-text").textContent = data.style_guide;
    refreshStatus();
  } catch (e) {
    alert("エラー: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "文体を分析";
  }
});

$("#btn-refresh-stats").addEventListener("click", async () => {
  const el = $("#stats-content");
  el.innerHTML = '<p class="muted">読込中...</p>';
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    let html = `<p>総記事数: <strong>${data.total}</strong> 件</p>`;
    html += "<p><strong>年別記事数</strong></p><div>";
    for (const [year, cnt] of Object.entries(data.by_year || {})) {
      const barWidth = Math.min(100, cnt * 2);
      html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;font-size:0.85rem">
        <span style="width:50px">${year}</span>
        <div style="background:var(--accent-soft);height:14px;width:${barWidth}px;border-radius:3px"></div>
        <span class="muted">${cnt}件</span>
      </div>`;
    }
    html += "</div>";
    html += `<p style="margin-top:12px"><strong>頻出キーワード</strong></p>`;
    html += `<p class="muted">${(data.top_keywords || []).join("、")}</p>`;

    el.innerHTML = html;
  } catch (e) {
    showError(el, e.message);
  }
});

// ---------- テーマ提案 ----------
$("#btn-suggest").addEventListener("click", async () => {
  const focus = $("#suggest-focus").value;
  const n = parseInt($("#suggest-n").value) || 10;
  const loading = $("#suggest-loading");
  const results = $("#suggest-results");
  loading.style.display = "block";
  results.innerHTML = "";

  try {
    const res = await fetch("/api/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ focus, n }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    data.themes.forEach(t => {
      const card = document.createElement("div");
      card.className = "theme-card";
      card.innerHTML = `
        <h3>${escapeHtml(t.title)}</h3>
        <p>${escapeHtml(t.description || "")}</p>
        <div class="kw">${(t.keywords || []).join(", ")}</div>
      `;
      card.addEventListener("click", () => {
        $$(".tab-btn").forEach(b => b.classList.remove("active"));
        $$(".tab-panel").forEach(p => p.classList.remove("active"));
        document.querySelector('[data-tab="generate"]').classList.add("active");
        $("#tab-generate").classList.add("active");
        $("#gen-theme").value = t.title;
      });
      results.appendChild(card);
    });
  } catch (e) {
    showError(results, e.message);
  } finally {
    loading.style.display = "none";
  }
});

// ---------- 記事生成 ----------
$("#btn-generate").addEventListener("click", async () => {
  const theme = $("#gen-theme").value.trim();
  if (!theme) { alert("テーマを入力してください。"); return; }

  const instruction = $("#gen-instruction").value;
  const refs = parseInt($("#gen-refs").value) || 5;
  const useStyle = $("#gen-style").checked;

  const loading = $("#gen-loading");
  const resultCard = $("#gen-result");
  loading.style.display = "block";
  resultCard.style.display = "none";

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme, instruction, refs, use_style_guide: useStyle }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    $("#gen-saved-path").textContent = `保存先: ${data.saved_path}`;
    $("#gen-refs-list").innerHTML = data.refs.map(r =>
      `<div>[${r.score ?? "-"}] ${escapeHtml(r.title)} (${r.date || ""})</div>`
    ).join("");
    $("#gen-article").textContent = data.article;
    resultCard.style.display = "block";
  } catch (e) {
    resultCard.style.display = "block";
    showError($("#gen-article"), e.message);
    $("#gen-saved-path").textContent = "";
    $("#gen-refs-list").innerHTML = "";
  } finally {
    loading.style.display = "none";
  }
});

// ---------- 一括生成 ----------
$("#btn-batch").addEventListener("click", async () => {
  const raw = $("#batch-themes").value;
  const themes = raw.split("\n").map(s => s.trim()).filter(s => s && !s.startsWith("#"));
  if (themes.length === 0) { alert("テーマを入力してください。"); return; }

  const loading = $("#batch-loading");
  const resultCard = $("#batch-results");
  const list = $("#batch-list");
  loading.style.display = "block";
  resultCard.style.display = "none";
  list.innerHTML = "";

  try {
    const res = await fetch("/api/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ themes }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    data.results.forEach(r => {
      const li = document.createElement("li");
      li.textContent = `${r.theme} → ${r.path}`;
      list.appendChild(li);
    });
    resultCard.style.display = "block";
  } catch (e) {
    resultCard.style.display = "block";
    showError(list, e.message);
  } finally {
    loading.style.display = "none";
  }
});

// ---------- 検索 ----------
async function doSearch() {
  const q = $("#search-query").value.trim();
  if (!q) return;
  const el = $("#search-results");
  el.innerHTML = '<p class="muted">検索中...</p>';

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&top=10`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    if (data.results.length === 0) {
      el.innerHTML = '<p class="muted">該当する記事が見つかりませんでした。</p>';
      return;
    }

    el.innerHTML = data.results.map(r => `
      <div class="search-item">
        <span class="score">${r.score}</span>${r.date || ""}
        <h4>${escapeHtml(r.title)}</h4>
        <p>${escapeHtml(r.preview || "")}</p>
      </div>
    `).join("");
  } catch (e) {
    showError(el, e.message);
  }
}

$("#btn-search").addEventListener("click", doSearch);
$("#search-query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
});

// ---------- 生成履歴 ----------
async function refreshOutputs() {
  const list = $("#output-list");
  list.innerHTML = '<li class="muted">読込中...</li>';
  try {
    const res = await fetch("/api/outputs");
    const data = await res.json();
    list.innerHTML = "";
    data.files.forEach(f => {
      const li = document.createElement("li");
      li.textContent = f.name;
      li.addEventListener("click", async () => {
        $$("#output-list li").forEach(el => el.classList.remove("active"));
        li.classList.add("active");
        const viewer = $("#output-viewer");
        viewer.textContent = "読込中...";
        const r = await fetch(`/api/outputs/${encodeURIComponent(f.path.split("/").pop())}`);
        const d = await r.json();
        viewer.textContent = d.content || d.error;
      });
      list.appendChild(li);
    });
  } catch (e) {
    list.innerHTML = "";
    showError(list, e.message);
  }
}

$("#btn-refresh-outputs").addEventListener("click", refreshOutputs);

// ---------- 初期化 ----------
refreshStatus();
refreshOutputs();
