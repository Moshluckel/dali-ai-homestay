const HOTEL_ID = "hotel_demo";
function makeSessionId() {
  try {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
  } catch (e) {}
  return "sess-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
}

let sessionId = localStorage.getItem("dali_ai_demo_session") || makeSessionId();
localStorage.setItem("dali_ai_demo_session", sessionId);

const chat = document.getElementById("chat");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");

fetch(`/api/hotel/${HOTEL_ID}`)
  .then(r => r.json())
  .then(h => document.getElementById("hotelName").textContent = h.short_name)
  .catch(() => {});

function scrollBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function userBubble(text) {
  const el = document.createElement("div");
  el.className = "bubble user";
  el.innerHTML = `<div>${escapeHtml(text)}</div>`;
  chat.appendChild(el);
}

function assistantBubble(text, source) {
  const el = document.createElement("div");
  el.className = "bubble assistant";
  el.innerHTML = `
    <div class="avatar">风</div>
    <div>
      <p>${escapeHtml(text)}</p>
      <span class="source">${escapeHtml(source || "AI在地管家")}</span>
    </div>`;
  chat.appendChild(el);
}

function addCards(cards) {
  if (!cards || !cards.length) return;
  const wrap = document.createElement("div");
  wrap.className = "cards";
  cards.forEach(card => {
    const el = document.createElement("div");
    el.className = "reco-card";
    const verified = card.verified_at ? `最近核实：${card.verified_at}` : "";
    const route = card.route ? `<div class="meta">${escapeHtml(card.route)}</div>` : "";
    el.innerHTML = `
      <h3>${escapeHtml(card.title)}</h3>
      <div class="meta">${escapeHtml(card.meta || "")}</div>
      ${route}
      <p>${escapeHtml(card.description || "")}</p>
      <div class="verified">${escapeHtml(verified)}</div>
      <button data-id="${escapeHtml(card.id)}" data-type="${escapeHtml(card.type)}">${escapeHtml(card.cta || "查看")}</button>`;
    el.querySelector("button").addEventListener("click", async () => {
      await fetch("/api/event", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          hotel_id:HOTEL_ID,
          session_id:sessionId,
          event_name:"recommendation_clicked",
          payload:{id:card.id, type:card.type}
        })
      }).catch(() => {});
      alert(card.type === "experience"
        ? "Demo：真实上线后这里进入咨询/预约流程。"
        : "Demo：真实上线后这里打开高德导航或地点详情。");
    });
    wrap.appendChild(el);
  });
  chat.appendChild(wrap);
}

function addHandoff() {
  const el = document.createElement("div");
  el.className = "handoff";
  el.textContent = "已进入人工处理场景。V1 中前台会收到消息卡片和会话上下文。";
  chat.appendChild(el);
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[m]));
}

async function send(text) {
  text = (text || input.value).trim();
  if (!text) return;
  input.value = "";
  userBubble(text);
  scrollBottom();

  sendBtn.disabled = true;
  sendBtn.textContent = "…";

  try {
    const r = await fetch("/api/chat", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({hotel_id:HOTEL_ID, session_id:sessionId, message:text})
    });
    const data = await r.json();
    const sourceNames = {
      hotel_fact:"来自店铺确认资料",
      verified_poi_db:"来自大理可信POI库",
      experience_db:"来自已录入体验库",
      safety_rule:"安全规则 · 已转人工",
      llm_with_verified_context:"AI组织表达 · 基于已核实上下文",
      safe_fallback:"信息不足 · 建议人工确认"
    };
    assistantBubble(data.text, sourceNames[data.source_type] || data.source_type);
    addCards(data.cards);
    if (data.handoff) addHandoff();
  } catch (e) {
    assistantBubble("网络出了点问题，请稍后再试。", "系统");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "发送";
    scrollBottom();
    input.focus();
  }
}

sendBtn.addEventListener("click", () => send());
input.addEventListener("keydown", e => {
  if (e.key === "Enter") send();
});
document.querySelectorAll("[data-q]").forEach(btn => {
  btn.addEventListener("click", () => send(btn.dataset.q));
});
