const HOTEL_ID = "hotel_demo";

async function load() {
  const [stats, faqs, messages] = await Promise.all([
    fetch(`/api/admin/stats/${HOTEL_ID}`).then(r => r.json()),
    fetch(`/api/admin/faqs/${HOTEL_ID}`).then(r => r.json()),
    fetch(`/api/admin/messages/${HOTEL_ID}`).then(r => r.json())
  ]);

  document.getElementById("sSessions").textContent = stats.sessions;
  document.getElementById("sMessages").textContent = stats.user_messages;
  document.getElementById("sFaq").textContent = stats.faq_answers;
  document.getElementById("sHandoff").textContent = stats.handoffs;
  document.getElementById("sPoi").textContent = stats.poi_recommendations;
  document.getElementById("sExp").textContent = stats.experience_recommendations;

  const faqList = document.getElementById("faqList");
  faqList.innerHTML = faqs.map(f => `
    <div class="faq-row">
      <strong>${escapeHtml(f.question)}</strong>
      <p>${escapeHtml(f.answer)}</p>
    </div>`).join("");

  const messageList = document.getElementById("messageList");
  if (!messages.length) {
    messageList.innerHTML = `<div class="message-row"><div class="message-content">还没有真实对话。先打开住客端问几个问题。</div></div>`;
  } else {
    messageList.innerHTML = messages.map(m => `
      <div class="message-row">
        <div class="message-role">${m.role === "user" ? "住客" : "AI"}</div>
        <div class="message-content">${escapeHtml(m.content)}</div>
        <div class="message-meta">${escapeHtml(m.source_type || "")}<br>${escapeHtml(m.intent || "")}</div>
      </div>`).join("");
  }
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[m]));
}

load().catch(console.error);
setInterval(() => load().catch(() => {}), 5000);
