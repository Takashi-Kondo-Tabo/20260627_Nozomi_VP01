import {
  createRoom,
  getRoom,
  updateRoom,
  joinRoom,
  updateParticipant,
  advanceRoomStatus,
  submitPraise,
  subscribeRoom,
  subscribeParticipants,
  subscribePraises,
  newParticipantId,
} from "./kukai-db.js";

// 1人用（index.html）と同じキー。同じ端末ならAPIキー・モデル設定を引き継げる。
const STORAGE_KEY_API = "haiku_app_api_key";
const STORAGE_KEY_MODEL = "haiku_app_model";
const PROFILE_KEY = "haiku-kukai:profile";
const participantKey = (roomId) => `haiku-kukai:participant:${roomId}`;

const EMOJI_OPTIONS = ["🌸", "🍁", "🌙", "❄️", "🎐", "🐸", "🦋", "🐱", "🐤", "🍵", "🖌️", "⛩️", "🌊", "🍡", "⭐"];

const PRAISE_POINTS = [
  "情景が目に浮かぶ",
  "季語が効いている",
  "言葉選びが好き",
  "リズムが心地よい",
  "余韻が残る",
  "共感した",
  "発想がユニーク",
  "ちょいたしが活きている",
];

const MODELS = [
  { value: "claude-sonnet-5", label: "Claude Sonnet 5（バランス型・推奨）" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5（高速・低コスト）" },
  { value: "claude-opus-4-8", label: "Claude Opus 4.8（最高品質）" },
];

// Keep this list in sync with CARD_DECK in index.html and cards.html.
const CARD_DECK = [
  { icon: '📰', title: '一文字が語る、時の流れ', tip: '今日目にした新聞やニュースの見出しから、ふと心に残った一語を句に取り入れてみましょう。日々の積み重ねが「時」を語りだします。' },
  { icon: '🖋️', title: '名詞止めもイイネ', tip: '動詞や「〜だ」で終わらせず、名詞（体言止め）で句をすっと締めくくってみましょう。余韻がぐっと深まります。' },
  { icon: '📅', title: '昨日あったこと', tip: '特別な出来事でなくて構いません。昨日ふと感じた小さな一場面を、句のどこかに紛れ込ませてみましょう。' },
  { icon: '🌱', title: '1ミリの想いが語る', tip: 'ほんの小さな、言葉にしづらい気持ちを句に忍ばせてみましょう。季語（例:「春陽」）と組み合わせると、そっと寄り添います。' },
  { icon: '🌈', title: '色を一つ足す', tip: '俳句の中に色彩を表す言葉（紅、白、青など）を一つ加えてみましょう。' },
  { icon: '👂', title: '音を聞いてみる', tip: '鳥の声、雨音、電車の音など、聞こえてくる音を一つ描写に加えてみましょう。' },
  { icon: '✋', title: '肌で感じる', tip: '冷たい、温かい、柔らかいなど、肌で感じる感覚を一語入れてみましょう。' },
  { icon: '🔍', title: '名前を具体的に', tip: '「花」を「桜」、「鳥」を「雀」のように、より具体的な名前に置き換えてみましょう。' },
  { icon: '⏳', title: '時間をひとさじ', tip: '「夕暮れ」「明け方」など、時間の流れを感じさせる言葉を入れてみましょう。' },
  { icon: '🎭', title: '風に人格を', tip: '自然物を人のように表現してみましょう（例:「風が笑う」）。' },
  { icon: '⚖️', title: '静と動を並べる', tip: '静かなものと動くものを、句の中で対比させてみましょう。' },
  { icon: '✂️', title: '「や・かな・けり」を一つ', tip: '切れ字（や・かな・けり）を使い、句に余韻を作ってみましょう。' },
  { icon: '🖼️', title: '言わずに残す', tip: 'すべてを説明せず、一部を読み手の想像に委ねてみましょう。' },
  { icon: '🔢', title: '数をひとつ', tip: '「一つ」「三羽」など、具体的な数を入れると情景が締まります。' },
  { icon: '👀', title: '近くに寄ってみる', tip: '遠くから見た景色から、すぐそばの小さなものへ視点を移してみましょう。' },
  { icon: '🍃', title: '季語を主役に', tip: '季語をもっと句の中心に据えてみましょう。' },
  { icon: '🤫', title: '動詞をひとつ引く', tip: '動詞を一つ減らし、名詞の並びだけで情景を描いてみましょう。' },
  { icon: '🌙', title: '音のない一瞬', tip: '物音のしない、静かな瞬間を切り取ってみましょう。' },
  { icon: '💭', title: '気持ちの言葉を消す', tip: '「嬉しい」「悲しい」のような感情語を消し、情景だけで気持ちをにおわせてみましょう。' },
  { icon: '💗', title: '心に残ることは?', tip: 'いちばん心に残ったことは何か、句の種にしてみましょう。' },
  { icon: '😄', title: 'とびきり嬉しかったこと', tip: '最近（今日や昨日）、嬉しかったことを句に忍ばせてみましょう。' },
  { icon: '😢', title: '悲しかった・さみしかったこと', tip: 'とても悲しかったこと、さみしかったことを句の種にしてみましょう。' },
  { icon: '🔁', title: '言いかえると?', tip: '同じ意味でも、別の言葉に言いかえられないか考えてみましょう。' },
  { icon: '🔗', title: '季語と残りの音、共通点ある?', tip: '季語と、それ以外の十二音のあいだに共通点を持たせてみましょう。' },
  { icon: '👅', title: 'どんな味?', tip: 'その情景にはどんな味がするか、想像して加えてみましょう。' },
  { icon: '🧑', title: '詠み手はどんな人柄?', tip: 'この句を詠んだ人はどんな人柄か、想像しながら言葉を選んでみましょう。' },
  { icon: '🎐', title: 'オノマトペを使ってみる', tip: '「しとしと」「じんじん」のような擬音・擬態語を入れてみましょう。' },
  { icon: '🍛', title: '具体的なモノがある?', tip: '抽象的な言葉ではなく、目に見える具体的なモノを句に入れてみましょう。' },
  { icon: '🎵', title: '余韻はある?', tip: '読み終えたあと、余韻が残る言葉で締めくくれているか確かめてみましょう。' },
  { icon: '🗣️', title: '声に出して詠んでみる', tip: '実際に声に出して読み、心地よい調べになっているか確かめてみましょう。' },
  { icon: '💬', title: '「モノ」に語ってもらう', tip: '句の中のモノ自身が語っているように詠んでみましょう。' },
  { icon: '🎨', title: '絵になる景色が浮かぶ?', tip: '一枚の絵や写真のように、景色がはっきり思い浮かぶか確かめてみましょう。' },
  { icon: '🔡', title: '助詞にこだわる', tip: '「に」「が」「は」など、助詞ひとつで印象が変わることを意識してみましょう。' },
  { icon: '✨', title: 'オリジナリティは?', tip: '誰も書きそうにない、自分だけの視点や言葉を探してみましょう。' },
  { icon: '❓', title: '違和感はある?', tip: '読み返して、しっくりこない言葉や違和感がないか確かめてみましょう。' },
  { icon: '🕰️', title: 'いつ・どこは季語にまかせる', tip: '「いつ」「どこで」をあえて言わず、季語にその役割をゆだねてみましょう。' },
  { icon: '👃', title: '香り・におい', tip: 'その場に漂う香りやにおいを句に加えてみましょう。' },
  { icon: '🗑️', title: '省ける情報はない?', tip: '無くても伝わる言葉を削り、ワンシーンに絞り込めないか考えてみましょう。' },
  { icon: '😌', title: 'カッコつけない', tip: '格好つけず、思ったことをそのまま素直に出してみましょう。' },
  { icon: '📷', title: '過去の思い出に置き換える', tip: '今の情景を、過去の似た思い出に置き換えてみましょう（過去形にはせず、新鮮さは保って）。' },
  { icon: '📦', title: '「コト」ではなく「モノ」を詠む', tip: '出来事（コト）そのものではなく、そこにあった物（モノ）を詠んでみましょう。' },
];

const SCORE_SYSTEM = `あなたは俳句の専門家審査員です。与えられた俳句を10点満点で採点してください。
採点基準: 季語の有無と効果的な使用、五七五のリズム、情景の鮮明さ、独創性・意外性、余韻の深さ。
句に季語が含まれていれば、その季語と、季節・意味・情景を説明する解説文も添えてください。季語が無ければ空文字にしてください。
出力は必ず次のJSON形式のみで返してください。説明文やマークダウンのコードブロックは一切付けないこと。
{"score": 数値(0から10、小数点1桁まで可), "goodPoint": "良い点を一文で", "improvement": "さらに良くするヒントを一文で", "kigo": "句に含まれる季語（無ければ空文字）", "kigoDescription": "その季語の季節・意味・情景を説明する解説文を一文で（季語が無ければ空文字）"}`;

const HINT_SYSTEM = `あなたは句会の世話役です。参加者全員が同じお題で一句ずつ詠むための「お題」を一つ作ってください。
季語を一つと、着想のテーマ、情景のヒント、作句のコツを簡潔に示してください。
季節や題材は毎回ランダムに変えてください。
出力は必ず次のJSON形式のみで返してください。説明文やマークダウンのコードブロックは一切付けないこと。
{"kigo": "季語", "theme": "テーマ（例: 夏の夕暮れの静けさ）", "sceneHint": "情景のヒントを一〜二文で", "techniqueTip": "作句のコツを一文で"}`;

const app = document.getElementById("app");

const state = {
  roomId: null,
  participantId: null,
  room: null,
  participants: [],
  praises: [],
  selectedEmoji: EMOJI_OPTIONS[0],
  apiKey: localStorage.getItem(STORAGE_KEY_API) || "",
  model: localStorage.getItem(STORAGE_KEY_MODEL) || "claude-sonnet-5",
  promptDraft: { kigo: "", theme: "", sceneHint: "", techniqueTip: "" },
  hintLoading: false,
  hostError: "",
  draft1: "",
  draft2: null,
  praiseDraft: { points: [], comment: "" },
  busy: false,
  error: "",
};

let lastScreenKey = null;
let unsubscribers = [];
let scoringInFlight = false;
// 自分の書き込みが参加者リストに反映される前に別のスナップショット（部屋など）が届くと、
// 採点済みの句が未採点に見えて二重にAPIを呼んでしまう。この端末で採点した句を覚えておく。
const scoredHere = new Set();

// ---------- utilities ----------
function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function loadProfile() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_KEY)) || {};
  } catch {
    return {};
  }
}

function saveProfile(profile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

function me() {
  return state.participants.find((p) => p.id === state.participantId) || null;
}

function isHost() {
  return !!state.room && state.room.hostId === state.participantId;
}

function hostParticipant() {
  return state.participants.find((p) => p.id === state.room?.hostId) || null;
}

function formatDelta(delta) {
  if (delta > 0.001) return { cls: "up", text: `▲+${delta.toFixed(1)}` };
  if (delta < -0.001) return { cls: "down", text: `▼${delta.toFixed(1)}` };
  return { cls: "flat", text: "→±0" };
}

function drawCard(excludeTitle) {
  const pool = CARD_DECK.filter((c) => c.title !== excludeTitle);
  return pool[Math.floor(Math.random() * pool.length)];
}

// ---------- Claude API（ホスト端末のみが呼ぶ） ----------
// Claude sometimes emits a raw newline/tab inside a JSON string value instead of the
// escaped \n. That's invalid JSON, so escape stray control characters inside strings.
function escapeStrayControlChars(str) {
  let result = "";
  let inString = false;
  let escaped = false;
  for (const ch of str) {
    if (inString) {
      if (escaped) { result += ch; escaped = false; continue; }
      if (ch === "\\") { result += ch; escaped = true; continue; }
      if (ch === '"') { result += ch; inString = false; continue; }
      if (ch === "\n") { result += "\\n"; continue; }
      if (ch === "\r") continue;
      if (ch === "\t") { result += "\\t"; continue; }
      result += ch;
    } else {
      if (ch === '"') inString = true;
      result += ch;
    }
  }
  return result;
}

function extractJSON(text) {
  const cleaned = (text || "").trim().replace(/^```(json)?/i, "").replace(/```$/, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  const parseError = () => {
    const err = new Error("AIの応答を解析できませんでした。もう一度お試しください。");
    err.isParseError = true;
    return err;
  };
  if (start === -1 || end === -1) throw parseError();
  const jsonStr = cleaned.slice(start, end + 1);
  try {
    return JSON.parse(jsonStr);
  } catch {
    try {
      return JSON.parse(escapeStrayControlChars(jsonStr));
    } catch {
      throw parseError();
    }
  }
}

async function callClaudeOnce(system, userText, maxTokens) {
  if (!state.apiKey) throw new Error("ホストの設定欄でAnthropic APIキーを入力してください。");
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": state.apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model: state.model,
      max_tokens: maxTokens,
      system,
      messages: [{ role: "user", content: userText }],
    }),
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).error?.message || ""; } catch {}
    throw new Error(`APIエラー (${res.status}) ${detail}`);
  }
  const data = await res.json();
  return extractJSON((data.content || []).map((c) => c.text || "").join(""));
}

// JSONが崩れて返ることが稀にあるため、解析失敗だけは黙って1回だけ再試行する。
async function callClaude(system, userText, maxTokens = 500) {
  try {
    return await callClaudeOnce(system, userText, maxTokens);
  } catch (e) {
    if (!e.isParseError) throw e;
    return await callClaudeOnce(system, userText, maxTokens);
  }
}

function normalizeScore(r) {
  const n = Number(r.score);
  return {
    score: Number.isFinite(n) ? Math.round(Math.max(0, Math.min(10, n)) * 10) / 10 : 0,
    goodPoint: String(r.goodPoint || ""),
    improvement: String(r.improvement || ""),
    kigo: String(r.kigo || ""),
    kigoDescription: String(r.kigoDescription || ""),
  };
}

// 採点フェーズ中、ホスト端末が未採点の句を順に採点する。途中でホストが再読み込みしても
// 採点済み（aiN が入っている）の句は飛ばすので、そのまま再開できる。
// 部屋と参加者は別々のリスナーで届くため、「採点へ進んだ」通知が最後の投句より先に着くことがある。
// 本文がまだ届いていない句は飛ばし、次のスナップショットで採点する。
async function runHostScoring() {
  if (!isHost() || scoringInFlight || state.hostError) return;
  const round = { scoring1: 1, scoring2: 2 }[state.room.status];
  if (!round) return;
  const pending = state.participants.filter((p) =>
    !p[`ai${round}`] && p[`text${round}`] && !scoredHere.has(`${state.roomId}:${round}:${p.id}`));
  if (pending.length === 0) return;
  scoringInFlight = true;
  try {
    for (const p of pending) {
      const result = normalizeScore(await callClaude(SCORE_SYSTEM, p[`text${round}`]));
      await updateParticipant(state.roomId, p.id, { [`ai${round}`]: result });
      scoredHere.add(`${state.roomId}:${round}:${p.id}`);
    }
  } catch (e) {
    console.error(e);
    state.hostError = e.message;
    forceRender();
  } finally {
    scoringInFlight = false;
  }
}

// ---------- room connection & phase control ----------
function cleanupSubscriptions() {
  unsubscribers.forEach((u) => u());
  unsubscribers = [];
}

function connectToRoom(roomId, participantId) {
  cleanupSubscriptions();
  state.roomId = roomId;
  state.participantId = participantId;
  location.hash = roomId;
  unsubscribers.push(subscribeRoom(roomId, (room) => { state.room = room; onSnapshotUpdate(); }));
  unsubscribers.push(subscribeParticipants(roomId, (list) => { state.participants = list; onSnapshotUpdate(); }));
  unsubscribers.push(subscribePraises(roomId, (list) => { state.praises = list; onSnapshotUpdate(); }));
}

function onSnapshotUpdate() {
  maybeAdvancePhase();
  runHostScoring();
  render();
}

async function maybeAdvancePhase() {
  if (!state.room) return;
  const ps = state.participants;
  const n = ps.length;
  if (n === 0) return;
  const next = {
    composing: ps.every((p) => p.submitted1) && "scoring1",
    scoring1: ps.every((p) => p.ai1) && "brushup",
    brushup: ps.every((p) => p.submitted2) && "scoring2",
    scoring2: ps.every((p) => p.ai2) && "praising",
    praising: n > 1 && state.praises.length >= n * (n - 1) && "results",
  }[state.room.status];
  if (next) await advanceRoomStatus(state.roomId, state.room.status, next);
}

function remainingPraiseTargets() {
  const done = new Set(state.praises.filter((p) => p.raterId === state.participantId).map((p) => p.targetId));
  return state.participants.filter((p) => p.id !== state.participantId && !done.has(p.id));
}

// 他の人の入力で画面全体を描き直すと、入力中のテキストが消えてしまう。
// 自分の画面の中身が変わるときだけ描き直し、それ以外は進捗表示だけ差し替える。
function computeScreenKey() {
  if (!state.roomId) return "home";
  // 再読み込み直後は部屋が先に届き、自分の参加者データが後から届く。揃うまでは描かない。
  const m = me();
  if (!state.room || !m) return "loading";
  const s = state.room.status;
  switch (s) {
    case "waiting": return `waiting:${state.hintLoading}:${state.hostError}:${hostParticipant()?.name || ""}`;
    case "composing": return `composing:${!!m.submitted1}`;
    case "scoring1":
    case "scoring2": return `${s}:${state.hostError}`;
    case "brushup": return `brushup:${!!m.ai1}:${!!m.submitted2}:${m.card?.title || ""}:${!!m.cardSwapped}`;
    case "praising": return `praising:${remainingPraiseTargets()[0]?.id || "done"}`;
    case "results": return `results:${state.participants.filter((p) => p.ai2).length}:${state.praises.length}`;
    default: return s;
  }
}

function forceRender() {
  lastScreenKey = null;
  render();
}

function render() {
  const key = computeScreenKey();
  if (key === lastScreenKey) {
    patchLive();
    return;
  }
  lastScreenKey = key;
  let body;
  if (!state.roomId) body = renderHome();
  else if (key === "loading") body = `<div class="loading"><div class="spinner"></div>読み込み中…</div>`;
  else {
    body = {
      waiting: renderLobby,
      composing: renderComposing,
      scoring1: renderScoring,
      scoring2: renderScoring,
      brushup: renderBrushup,
      praising: renderPraising,
      results: renderResults,
    }[state.room.status]();
  }
  app.innerHTML = `
    <header class="top">
      <h1>俳句道場 <span class="mode-badge">句会モード</span></h1>
      <p>みんなで詠んで、ちょいたしカードで磨いて、褒め合う一句</p>
    </header>
    ${key !== "home" && key !== "loading" ? renderStepper() : ""}
    ${body}
    <footer class="foot">五七五の心で、今日の一句を。</footer>
  `;
  patchLive();
}

function patchLive() {
  const ps = state.participants;
  const n = ps.length;
  const set = (id, html) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  };
  set("memberList", renderMemberChips());
  set("memberCount", `${n} 人が参加中`);
  const startBtn = document.getElementById("startBtn");
  if (startBtn) startBtn.disabled = !canStart();
  set("startHint", startHintText());
  if (!state.room) return;
  const s = state.room.status;
  if (s === "composing") set("liveCount", `詠み終えた人 ${ps.filter((p) => p.submitted1).length} / ${n}`);
  if (s === "brushup") set("liveCount", `推敲を終えた人 ${ps.filter((p) => p.submitted2).length} / ${n}`);
  if (s === "scoring1" || s === "scoring2") {
    const round = s === "scoring1" ? 1 : 2;
    set("liveCount", `採点済み ${ps.filter((p) => p[`ai${round}`]).length} / ${n}`);
  }
  if (s === "praising") set("liveCount", `褒め言葉 ${state.praises.length} / ${n * (n - 1)}`);
}

// ---------- shared fragments ----------
const STEPS = [
  { key: "waiting", label: "集合" },
  { key: "composing", label: "詠む" },
  { key: "scoring1", label: "採点" },
  { key: "brushup", label: "ちょいたし" },
  { key: "scoring2", label: "再採点" },
  { key: "praising", label: "褒め合う" },
  { key: "results", label: "結果" },
];

function renderStepper() {
  const current = STEPS.findIndex((s) => s.key === state.room.status);
  return `<ol class="stepper">${STEPS.map((s, i) =>
    `<li class="${i < current ? "done" : i === current ? "now" : ""}">${s.label}</li>`).join("")}</ol>`;
}

function renderPromptBox(prompt) {
  if (!prompt) return "";
  return `
    <div class="hint-box">
      <div class="row-item"><b>季語:</b> ${escapeHtml(prompt.kigo)}</div>
      ${prompt.theme ? `<div class="row-item"><b>テーマ:</b> ${escapeHtml(prompt.theme)}</div>` : ""}
      ${prompt.sceneHint ? `<div class="row-item"><b>情景のヒント:</b> ${escapeHtml(prompt.sceneHint)}</div>` : ""}
      ${prompt.techniqueTip ? `<div class="row-item"><b>作句のコツ:</b> ${escapeHtml(prompt.techniqueTip)}</div>` : ""}
    </div>`;
}

function renderMemberChips() {
  return state.participants.map((p) =>
    `<span class="member">${p.emoji} ${escapeHtml(p.name)}${p.id === state.room?.hostId ? '<small>ホスト</small>' : ""}</span>`).join("");
}

function renderWaitBox(icon, message) {
  return `
    <div class="panel center">
      <div class="big-icon">${icon}</div>
      <p>${message}</p>
      <p id="liveCount" class="muted"></p>
    </div>`;
}

function renderErrorBox(msg) {
  return msg ? `<div class="error-box">⚠️ ${escapeHtml(msg)}</div>` : "";
}

function renderScoreBlock(text, ai) {
  const pct = Math.max(0, Math.min(100, ai.score * 10));
  return `
    <div class="haiku-display">${escapeHtml(text)}</div>
    <div class="score-wrap">
      <div class="score-num">${ai.score}<small>/10</small></div>
      <div class="score-bar-bg"><div class="score-bar-fill" style="width:${pct}%"></div></div>
    </div>
    <div class="comment-row"><span class="tag good">良い点</span><span>${escapeHtml(ai.goodPoint)}</span></div>
    <div class="comment-row"><span class="tag tip">ヒント</span><span>${escapeHtml(ai.improvement)}</span></div>
    ${ai.kigo ? `<div style="margin-top:8px;"><span class="kw-chip">季語: ${escapeHtml(ai.kigo)}</span></div>
      ${ai.kigoDescription ? `<p class="kigo-description">${escapeHtml(ai.kigoDescription)}</p>` : ""}` : ""}`;
}

// ---------- Home ----------
function renderHome() {
  const profile = loadProfile();
  const prefillCode = (location.hash || "").replace("#", "").toUpperCase();
  state.selectedEmoji = profile.emoji || state.selectedEmoji;
  return `
    <a class="back-link" href="index.html">← ひとりで詠むモードへ</a>
    <div class="panel">
      <label class="field-label">俳号（ニックネーム）</label>
      <input id="nameInput" type="text" maxlength="12" placeholder="例: 多ぁ望" value="${escapeHtml(profile.name || "")}">
      <div class="emoji-picker">
        ${EMOJI_OPTIONS.map((e) => `<button type="button" class="emoji-btn ${e === state.selectedEmoji ? "selected" : ""}" data-action="pickEmoji" data-emoji="${e}">${e}</button>`).join("")}
      </div>
    </div>
    <div class="mode-grid">
      <div class="panel center">
        <h3 class="serif panel-title">句会をひらく</h3>
        <p class="muted small">ホストになってルームを作ります。AIの採点はホストのAPIキーで行います。</p>
        <button class="btn btn-primary btn-block" data-action="createRoom" ${state.busy ? "disabled" : ""}>🏯 ルームをつくる</button>
      </div>
      <div class="panel center">
        <h3 class="serif panel-title">句会に参加する</h3>
        <input id="codeInput" type="text" maxlength="5" placeholder="ルームコード" value="${escapeHtml(prefillCode)}" class="code-input">
        <div style="height:10px;"></div>
        <button class="btn btn-ghost btn-block" data-action="joinRoom" ${state.busy ? "disabled" : ""}>参加する</button>
      </div>
    </div>
    ${renderErrorBox(state.error)}`;
}

function readName() {
  return document.getElementById("nameInput").value.trim();
}

async function createRoomAction() {
  const name = readName();
  if (!name) return showError("俳号を入力してください。");
  state.busy = true; state.error = ""; forceRender();
  try {
    saveProfile({ name, emoji: state.selectedEmoji });
    const participantId = newParticipantId();
    const roomId = await createRoom(participantId);
    await joinRoom(roomId, participantId, name, state.selectedEmoji);
    localStorage.setItem(participantKey(roomId), participantId);
    connectToRoom(roomId, participantId);
  } catch (e) {
    console.error(e);
    state.error = "ルームを作れませんでした。通信環境を確認してもう一度お試しください。";
  } finally {
    state.busy = false; forceRender();
  }
}

async function joinRoomAction() {
  const name = readName();
  const code = document.getElementById("codeInput").value.trim().toUpperCase();
  if (!name) return showError("俳号を入力してください。");
  if (!code) return showError("ルームコードを入力してください。");
  state.busy = true; state.error = ""; forceRender();
  try {
    const room = await getRoom(code);
    if (!room) throw userError("そのルームは見つかりませんでした。");
    if (room.status !== "waiting") throw userError("この句会はすでに始まっています。");
    saveProfile({ name, emoji: state.selectedEmoji });
    const participantId = newParticipantId();
    await joinRoom(code, participantId, name, state.selectedEmoji);
    localStorage.setItem(participantKey(code), participantId);
    connectToRoom(code, participantId);
  } catch (e) {
    console.error(e);
    state.error = e.isUserError ? e.message : "参加できませんでした。通信環境を確認してもう一度お試しください。";
  } finally {
    state.busy = false; forceRender();
  }
}

function userError(msg) {
  const err = new Error(msg);
  err.isUserError = true;
  return err;
}

function showError(msg) {
  state.error = msg;
  forceRender();
}

// ---------- Lobby ----------
function canStart() {
  return isHost() && state.participants.length >= 2 && !!state.apiKey && !!state.promptDraft.kigo.trim();
}

function startHintText() {
  if (!isHost()) return "";
  if (state.participants.length < 2) return "2人以上集まったら始められます。";
  if (!state.apiKey) return "APIキーを設定すると始められます。";
  if (!state.promptDraft.kigo.trim()) return "お題の季語を決めると始められます。";
  return "";
}

function renderLobby() {
  const code = state.roomId;
  const shareUrl = `${location.origin}${location.pathname}#${code}`;
  return `
    <div class="panel center">
      <p class="muted small" style="margin:0;">ルームコード</p>
      <div class="room-code">${code}</div>
      <p class="muted small">このコードか、下のURLを参加者に共有してください</p>
      <div class="share-url">${escapeHtml(shareUrl)}</div>
    </div>
    <div class="panel">
      <div class="panel-title" id="memberCount"></div>
      <div id="memberList" class="member-list"></div>
    </div>
    ${isHost() ? renderHostSetup() : `
      <div class="panel center">
        <div class="big-icon">🍵</div>
        <p>ホスト（${escapeHtml(hostParticipant()?.name || "")}）がお題を決めて始めるのを待っています…</p>
      </div>`}`;
}

function renderHostSetup() {
  const options = MODELS.map((m) => `<option value="${m.value}" ${m.value === state.model ? "selected" : ""}>${escapeHtml(m.label)}</option>`).join("");
  const d = state.promptDraft;
  return `
    <details class="panel settings" ${state.apiKey ? "" : "open"}>
      <summary>⚙️ 設定（Anthropic APIキー・モデル）${state.apiKey ? " - 設定済み" : " - 未設定"}</summary>
      <div class="row" style="margin-bottom:10px;">
        <div>
          <label class="field-label">Anthropic APIキー</label>
          <input type="password" placeholder="sk-ant-..." value="${escapeHtml(state.apiKey)}" data-bind="apiKey">
        </div>
        <div>
          <label class="field-label">使用モデル</label>
          <select data-bind="model">${options}</select>
        </div>
      </div>
      <p class="muted tiny">APIキーはホストの端末のブラウザ内（localStorage）にのみ保存され、参加者には共有されません。全員の句の採点はホストの端末から行います。</p>
    </details>
    <div class="panel">
      <div class="panel-title">📜 今日のお題</div>
      <button class="btn btn-ghost" data-action="aiPrompt" ${state.hintLoading ? "disabled" : ""}>${state.hintLoading ? "考えています…" : "🤖 AIにお題を出してもらう"}</button>
      ${renderErrorBox(state.hostError)}
      <div class="row" style="margin-top:12px;">
        <div>
          <label class="field-label">季語（必須）</label>
          <input type="text" placeholder="例: 秋風" value="${escapeHtml(d.kigo)}" data-bind="prompt.kigo">
        </div>
        <div>
          <label class="field-label">テーマ（任意）</label>
          <input type="text" placeholder="例: 帰り道のさみしさ" value="${escapeHtml(d.theme)}" data-bind="prompt.theme">
        </div>
      </div>
      ${d.sceneHint || d.techniqueTip ? `<div style="margin-top:10px;">${renderPromptBox({ ...d, kigo: d.kigo || "（未入力）" })}</div>` : ""}
    </div>
    <button id="startBtn" class="btn btn-accent btn-block" data-action="startKukai">🖌️ 句会をはじめる</button>
    <p id="startHint" class="muted small center"></p>`;
}

async function aiPromptAction() {
  state.hintLoading = true; state.hostError = ""; forceRender();
  try {
    const h = await callClaude(HINT_SYSTEM, "今日の句会のお題を一つください。");
    state.promptDraft = {
      kigo: String(h.kigo || ""),
      theme: String(h.theme || ""),
      sceneHint: String(h.sceneHint || ""),
      techniqueTip: String(h.techniqueTip || ""),
    };
  } catch (e) {
    state.hostError = e.message;
  } finally {
    state.hintLoading = false; forceRender();
  }
}

async function startKukaiAction(btn) {
  if (!canStart()) return;
  btn.disabled = true;
  const d = state.promptDraft;
  try {
    await updateRoom(state.roomId, {
      status: "composing",
      prompt: { kigo: d.kigo.trim(), theme: d.theme.trim(), sceneHint: d.sceneHint, techniqueTip: d.techniqueTip },
    });
  } catch (e) {
    console.error(e);
    btn.disabled = false;
    state.hostError = "開始できませんでした。通信環境を確認してもう一度お試しください。";
    forceRender();
  }
}

// ---------- Composing ----------
function renderComposing() {
  if (me()?.submitted1) return renderWaitBox("⏳", "みんなが詠み終えるのを待っています…");
  return `
    <div class="panel">
      <div class="panel-title">📜 お題</div>
      ${renderPromptBox(state.room.prompt)}
      <label class="field-label">あなたの一句（五七五で。改行で3行に分けてもOK）</label>
      <textarea rows="3" maxlength="60" placeholder="例: 秋風や&#10;誰も知らない&#10;駅のベンチ" data-bind="draft1">${escapeHtml(state.draft1)}</textarea>
      ${renderErrorBox(state.error)}
      <div style="height:12px;"></div>
      <button class="btn btn-primary btn-block" data-action="submit1">📝 この句で投句する</button>
      <p id="liveCount" class="muted small center"></p>
    </div>`;
}

async function submit1Action(btn) {
  const text = state.draft1.trim();
  if (!text) return showError("句を入力してください。");
  btn.disabled = true; state.error = "";
  try {
    await updateParticipant(state.roomId, state.participantId, { text1: text, submitted1: true });
  } catch (e) {
    console.error(e);
    btn.disabled = false;
    showError("送信できませんでした。通信環境を確認してもう一度お試しください。");
  }
}

// ---------- Scoring ----------
function renderScoring() {
  const round = state.room.status === "scoring1" ? "" : "推敲後の句を";
  if (isHost() && state.hostError) {
    return `
      <div class="panel center">
        <div class="big-icon">⚠️</div>
        <p>採点の途中でエラーが起きました。</p>
        ${renderErrorBox(state.hostError)}
        <button class="btn btn-primary" data-action="retryScoring">🔄 採点を再開する</button>
        <p id="liveCount" class="muted small"></p>
      </div>`;
  }
  return `
    <div class="panel center">
      <div class="spinner"></div>
      <p>AI先生が${round}採点しています…</p>
      <p id="liveCount" class="muted small"></p>
      ${isHost() ? `<p class="muted tiny">ホストの端末で採点しています。このページを閉じないでください。</p>` : ""}
    </div>`;
}

// ---------- Brushup ----------
function renderBrushup() {
  const m = me();
  // 「推敲へ進んだ」通知が自分の採点結果より先に届くことがある。
  if (!m.ai1) return renderWaitBox("⏳", "採点結果を受け取っています…");
  if (m.submitted2) return renderWaitBox("🍵", "みんなの推敲が終わるのを待っています…");
  if (state.draft2 === null) state.draft2 = m.text1;
  return `
    <div class="panel">
      <div class="panel-title">あなたの初句</div>
      ${renderScoreBlock(m.text1, m.ai1)}
    </div>
    <div class="panel">
      ${m.card ? `
        <div class="card-draw">
          <div class="icon">${m.card.icon}</div>
          <h4>🌸 ちょいたしカード:「${escapeHtml(m.card.title)}」</h4>
          <p>${escapeHtml(m.card.tip)}</p>
          ${m.cardSwapped ? `<p class="muted tiny" style="margin-top:10px;">カード交換は1回まで（使用済み）</p>`
            : `<button class="btn btn-ghost" style="margin-top:12px; background:#fffdf8;" data-action="swapCard">🔄 カード交換（1回まで）</button>`}
        </div>
        <label class="field-label">カードをヒントに、句をブラッシュアップしましょう</label>
        <textarea rows="3" maxlength="60" data-bind="draft2">${escapeHtml(state.draft2)}</textarea>
        ${renderErrorBox(state.error)}
        <div style="height:10px;"></div>
        <button class="btn btn-accent btn-block" data-action="submit2">✨ 推敲した句を出す</button>
      ` : `
        <div class="choitashi-logo">
          <div class="ct-word ct-main">ちょいたし</div>
          <div class="ct-line2"><span class="ct-doodles">🐱🐤</span><span class="ct-word ct-sub">カード</span></div>
          <div class="ct-credit">2026.07.18　制作：多ぁ望＋くるすてぃーぬ</div>
        </div>
        <button class="btn btn-accent btn-block" data-action="drawCard">🌸 ちょいたしカードを1枚引く</button>
      `}
      <p id="liveCount" class="muted small center"></p>
    </div>`;
}

async function drawCardAction(btn) {
  btn.disabled = true;
  try {
    await updateParticipant(state.roomId, state.participantId, { card: drawCard() });
  } catch (e) {
    console.error(e);
    btn.disabled = false;
  }
}

async function swapCardAction(btn) {
  btn.disabled = true;
  try {
    await updateParticipant(state.roomId, state.participantId, { card: drawCard(me().card?.title), cardSwapped: true });
  } catch (e) {
    console.error(e);
    btn.disabled = false;
  }
}

async function submit2Action(btn) {
  const text = (state.draft2 || "").trim();
  if (!text) return showError("句を入力してください。");
  btn.disabled = true; state.error = "";
  try {
    await updateParticipant(state.roomId, state.participantId, { text2: text, submitted2: true });
  } catch (e) {
    console.error(e);
    btn.disabled = false;
    showError("送信できませんでした。通信環境を確認してもう一度お試しください。");
  }
}

// ---------- Praising ----------
function renderPraising() {
  const remaining = remainingPraiseTargets();
  if (remaining.length === 0) return renderWaitBox("👏", "みんなが褒め終わるのを待っています…");
  const t = remaining[0];
  const others = state.participants.length - 1;
  const d = state.praiseDraft;
  return `
    <p class="muted small center">褒め合いタイム（あと ${remaining.length} / ${others} 人）</p>
    <div class="panel">
      <div class="panel-title">${t.emoji} ${escapeHtml(t.name)} さんの一句</div>
      <div class="haiku-display">${escapeHtml(t.text2)}</div>
      ${t.card ? `<p class="muted small center">ちょいたしカード: ${t.card.icon} ${escapeHtml(t.card.title)}</p>` : ""}
      <details class="muted small"><summary>推敲前の句を見る</summary><div class="history-haiku" style="margin-top:6px;">${escapeHtml(t.text1)}</div></details>
    </div>
    <div class="panel">
      <label class="field-label">どこが良かった？（1つ以上えらぶ）</label>
      <div class="chips">
        ${PRAISE_POINTS.map((p) => `<button type="button" class="chip ${d.points.includes(p) ? "selected" : ""}" data-action="togglePoint" data-point="${escapeHtml(p)}">${escapeHtml(p)}</button>`).join("")}
      </div>
      <label class="field-label" style="margin-top:12px;">ひとことメッセージ（任意）</label>
      <input type="text" maxlength="60" placeholder="例: 駅のベンチの一人の時間がしみました" value="${escapeHtml(d.comment)}" data-bind="praiseComment">
      ${renderErrorBox(state.error)}
      <div style="height:12px;"></div>
      <button class="btn btn-primary btn-block" data-action="submitPraise" data-target="${t.id}">👏 褒め言葉を贈る</button>
      <p id="liveCount" class="muted small center"></p>
    </div>`;
}

function togglePointAction(btn) {
  const point = btn.dataset.point;
  const pts = state.praiseDraft.points;
  state.praiseDraft.points = pts.includes(point) ? pts.filter((p) => p !== point) : [...pts, point];
  btn.classList.toggle("selected");
}

async function submitPraiseAction(btn) {
  const { points, comment } = state.praiseDraft;
  if (points.length === 0) return showError("良かったところを1つ以上えらんでください。");
  btn.disabled = true; state.error = "";
  try {
    await submitPraise(state.roomId, state.participantId, btn.dataset.target, points, comment.trim());
    state.praiseDraft = { points: [], comment: "" };
  } catch (e) {
    console.error(e);
    btn.disabled = false;
    showError("送信できませんでした。通信環境を確認してもう一度お試しください。");
  }
}

// ---------- Results ----------
function buildResults() {
  return state.participants.map((p) => {
    const received = state.praises.filter((pr) => pr.targetId === p.id);
    const pointCounts = {};
    received.forEach((pr) => pr.points.forEach((pt) => { pointCounts[pt] = (pointCounts[pt] || 0) + 1; }));
    const comments = received
      .filter((pr) => pr.comment)
      .map((pr) => ({ from: state.participants.find((x) => x.id === pr.raterId), comment: pr.comment }));
    const totalPoints = Object.values(pointCounts).reduce((a, b) => a + b, 0);
    return { ...p, delta: p.ai2.score - p.ai1.score, pointCounts, comments, totalPoints };
  });
}

function renderResults() {
  if (state.participants.some((p) => !p.ai1 || !p.ai2)) return renderWaitBox("⏳", "結果を集計しています…");
  const results = buildResults();
  const maxDelta = Math.max(...results.map((r) => r.delta));
  const maxPraise = Math.max(...results.map((r) => r.totalPoints));
  const names = (list) => list.map((r) => `${r.emoji} ${escapeHtml(r.name)}`).join("、");
  const ordered = [...results.filter((r) => r.id === state.participantId), ...results.filter((r) => r.id !== state.participantId)];
  return `
    <div class="awards">
      ${maxDelta > 0.001 ? `<div class="award"><div class="award-label">🌱 いちばん伸びた一句</div><div>${names(results.filter((r) => r.delta === maxDelta))}<span class="delta up">${formatDelta(maxDelta).text}</span></div></div>` : ""}
      <div class="award"><div class="award-label">👏 いちばん褒められた一句</div><div>${names(results.filter((r) => r.totalPoints === maxPraise))}<span class="delta flat">${maxPraise}ポイント</span></div></div>
    </div>
    ${ordered.map(renderResultCard).join("")}
    <button class="btn btn-ghost btn-block" data-action="leaveRoom">🔁 新しい句会をひらく</button>`;
}

function renderResultCard(r) {
  const delta = formatDelta(r.delta);
  const chips = Object.entries(r.pointCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([pt, c]) => `<span class="kw-chip">${escapeHtml(pt)} ×${c}</span>`).join("");
  return `
    <div class="panel result-card ${r.id === state.participantId ? "mine" : ""}">
      <div class="history-head" style="margin-bottom:8px;">
        <span class="panel-title" style="margin:0;">${r.emoji} ${escapeHtml(r.name)}${r.id === state.participantId ? "（あなた）" : ""}</span>
        <span class="delta ${delta.cls}">${delta.text}</span>
      </div>
      <div class="history-item">
        <div class="history-head"><span>初句</span><span>${r.ai1.score}/10</span></div>
        <div class="history-haiku">${escapeHtml(r.text1)}</div>
      </div>
      ${r.card ? `<div class="card-used">${r.card.icon} ちょいたしカード「${escapeHtml(r.card.title)}」</div>` : ""}
      ${renderScoreBlock(r.text2, r.ai2)}
      <div class="praise-box">
        <div class="field-label">みんなからの褒め言葉</div>
        <div>${chips || '<span class="muted small">—</span>'}</div>
        ${r.comments.map((c) => `<div class="comment-row"><span class="tag praise">${c.from?.emoji || ""} ${escapeHtml(c.from?.name || "")}</span><span>${escapeHtml(c.comment)}</span></div>`).join("")}
      </div>
    </div>`;
}

function leaveRoomAction() {
  cleanupSubscriptions();
  localStorage.removeItem(participantKey(state.roomId));
  Object.assign(state, {
    roomId: null, participantId: null, room: null, participants: [], praises: [],
    promptDraft: { kigo: "", theme: "", sceneHint: "", techniqueTip: "" },
    hostError: "", draft1: "", draft2: null, praiseDraft: { points: [], comment: "" }, error: "",
  });
  location.hash = "";
  forceRender();
}

// ---------- event wiring ----------
const ACTIONS = {
  pickEmoji(btn) {
    state.selectedEmoji = btn.dataset.emoji;
    document.querySelectorAll(".emoji-btn").forEach((b) => b.classList.toggle("selected", b === btn));
  },
  createRoom: createRoomAction,
  joinRoom: joinRoomAction,
  aiPrompt: aiPromptAction,
  startKukai: startKukaiAction,
  submit1: submit1Action,
  retryScoring() {
    state.hostError = "";
    forceRender();
    runHostScoring();
  },
  drawCard: drawCardAction,
  swapCard: swapCardAction,
  submit2: submit2Action,
  togglePoint: togglePointAction,
  submitPraise: submitPraiseAction,
  leaveRoom: leaveRoomAction,
};

app.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn || btn.disabled) return;
  ACTIONS[btn.dataset.action]?.(btn);
});

const BINDINGS = {
  apiKey(v) {
    state.apiKey = v;
    localStorage.setItem(STORAGE_KEY_API, v);
  },
  model(v) {
    state.model = v;
    localStorage.setItem(STORAGE_KEY_MODEL, v);
  },
  "prompt.kigo": (v) => { state.promptDraft.kigo = v; },
  "prompt.theme": (v) => { state.promptDraft.theme = v; },
  draft1: (v) => { state.draft1 = v; },
  draft2: (v) => { state.draft2 = v; },
  praiseComment: (v) => { state.praiseDraft.comment = v; },
};

function onBind(e) {
  const key = e.target.dataset?.bind;
  if (!key) return;
  BINDINGS[key](e.target.value);
  patchLive();
}
app.addEventListener("input", onBind);
app.addEventListener("change", onBind);

// ---------- init ----------
async function init() {
  const hashRoomId = (location.hash || "").replace("#", "").toUpperCase();
  if (hashRoomId) {
    const storedId = localStorage.getItem(participantKey(hashRoomId));
    if (storedId) {
      try {
        if (await getRoom(hashRoomId)) {
          connectToRoom(hashRoomId, storedId);
          return;
        }
      } catch (e) {
        console.error(e);
      }
    }
  }
  render();
}

init();
