const API_BASE = "/api/reminders";

// ========== State ==========
let reminders = [];
let refreshInterval = null;

// ========== Init ==========
document.addEventListener("DOMContentLoaded", () => {
  loadReminders();
  refreshInterval = setInterval(loadReminders, 5000);
  // Tab click handlers
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", function() {
      const t = this.getAttribute("data-tab") || "local";
      switchTab(t);
    });
  });
});

// ========== API ==========
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(`${API_BASE}${path}`, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Network error" }));
    throw new Error(err.detail || "Request failed");
  }
  return resp.json();
}

// ========== Load & Render ==========
async function loadReminders() {
  try {
    reminders = await api("GET", "");
    renderReminders();
  } catch (e) {
    console.error("Failed to load reminders:", e);
  }
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hours = String(d.getHours()).padStart(2, "0");
  const mins = String(d.getMinutes()).padStart(2, "0");
  return {
    date: `${month}/${day}`,
    time: `${hours}:${mins}`,
    full: `${month}/${day} ${hours}:${mins}`,
  };
}

function getRepeatLabel(type) {
  const labels = { daily: "每天", weekly: "每周", monthly: "每月" };
  return labels[type] || "";
}

function renderReminders() {
  const grid = document.getElementById("reminderGrid");
  const empty = document.getElementById("emptyState");

  if (reminders.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="big-icon">🔔</div>
        <h2>还没有提醒</h2>
        <p>点击右上角的「新增提醒」来创建你的第一个提醒吧！</p>
      </div>
    `;
    return;
  }

  let html = "";
  for (const r of reminders) {
    const dt = formatDate(r.reminder_time);
    const repeatLabel = r.is_repeating ? getRepeatLabel(r.repeat_type) : "";

    html += `
      <div class="reminder-card" data-id="${r.id}">
        <div class="time-block">
          <div class="time">${dt.time}</div>
          <div class="date">${dt.date}</div>
        </div>
        <div class="content">
          <div class="title">${escapeHtml(r.title)}</div>
          ${r.description ? `<div class="desc">${escapeHtml(r.description)}</div>` : ""}
          ${repeatLabel ? `<div class="repeat-info">🔄 ${repeatLabel}</div>` : ""}
          ${r.created_at ? `<div class="desc">创建: ${formatDate(r.created_at).full}</div>` : ""}
        </div>
        <span class="status-badge ${r.status}">${getStatusLabel(r.status)}</span>
        <div class="actions">
          <button class="btn-icon play-btn" onclick="testPlay(${r.id})" title="试听">🔊</button>
          <button class="btn-icon edit-btn" onclick="openEditModal(${r.id})" title="编辑">✏️</button>
          <button class="btn-icon delete-btn" onclick="deleteReminder(${r.id})" title="删除">🗑️</button>
        </div>
      </div>
    `;
  }
  grid.innerHTML = html;
}

function getStatusLabel(status) {
  const labels = { pending: "⏳ 待播放", played: "✅ 已播放", missed: "⏰ 已错过" };
  return labels[status] || status;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ========== CRUD ==========
async function saveReminder(event) {
  event.preventDefault();

  const editId = document.getElementById("editId").value;
  const title = document.getElementById("title").value.trim();
  const description = document.getElementById("description").value.trim();
  const date = document.getElementById("reminderDate").value;
  const time = document.getElementById("reminderTime").value;
  const isRepeating = document.getElementById("isRepeating").value === "1";
  const repeatType = document.getElementById("repeatType").value;

  if (!title) {
    showToast("请输入提醒内容", "error");
    return;
  }

  const reminderTime = `${date}T${time}`;

  const data = {
    title,
    description,
    reminder_time: reminderTime,
    is_repeating: isRepeating,
    repeat_type: isRepeating ? repeatType : "",
  };

  try {
    if (editId) {
      await api("PUT", `/${editId}`, data);
      showToast("提醒已更新 ✅", "success");
    } else {
      await api("POST", "", data);
      showToast("提醒已创建 🎉", "success");
    }
    closeModal();
    await loadReminders();
  } catch (e) {
    showToast("保存失败：" + e.message, "error");
  }
}

async function deleteReminder(id) {
  if (!confirm("确定要删除这个提醒吗？")) return;

  try {
    await api("DELETE", `/${id}`);
    showToast("提醒已删除 🗑️", "info");
    await loadReminders();
  } catch (e) {
    showToast("删除失败：" + e.message, "error");
  }
}

async function testPlay(id) {
  try {
    document.getElementById("nowPlaying").classList.add("active");
    await api("POST", `/${id}/test-play`);
    showToast("正在播放提醒语音 🔊", "info");
    setTimeout(() => {
      document.getElementById("nowPlaying").classList.remove("active");
    }, 5000);
  } catch (e) {
    showToast("播放失败：" + e.message, "error");
    document.getElementById("nowPlaying").classList.remove("active");
  }
}

// ========== Modal ==========
function openAddModal() {
  document.getElementById("modalTitle").textContent = "✏️ 新增提醒";
  document.getElementById("editId").value = "";
  document.getElementById("reminderForm").reset();
  document.getElementById("repeatTypeGroup").style.display = "none";

  const now = new Date();
  const localDate = now.toISOString().split("T")[0];
  const localTime = now.toTimeString().slice(0, 5);
  document.getElementById("reminderDate").value = localDate;
  document.getElementById("reminderTime").value = localTime;

  document.getElementById("modalOverlay").classList.add("active");
}

function openEditModal(id) {
  const r = reminders.find((x) => x.id === id);
  if (!r) return;

  document.getElementById("modalTitle").textContent = "✏️ 编辑提醒";
  document.getElementById("editId").value = r.id;
  document.getElementById("title").value = r.title;
  document.getElementById("description").value = r.description || "";

  const dt = new Date(r.reminder_time);
  const localDate = dt.toISOString().split("T")[0];
  const localTime = dt.toTimeString().slice(0, 5);
  document.getElementById("reminderDate").value = localDate;
  document.getElementById("reminderTime").value = localTime;

  document.getElementById("isRepeating").value = r.is_repeating ? "1" : "0";
  document.getElementById("repeatType").value = r.repeat_type || "daily";
  toggleRepeatType();

  document.getElementById("modalOverlay").classList.add("active");
}

function closeModal() {
  document.getElementById("modalOverlay").classList.remove("active");
}

function toggleRepeatType() {
  const show = document.getElementById("isRepeating").value === "1";
  document.getElementById("repeatTypeGroup").style.display = show ? "block" : "none";
}

// Close modal on overlay click
document.getElementById("modalOverlay").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeModal();
});

// Close modal with Escape key
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

// ========== Toast ==========
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ====== Board Reminders ======
const BOARD_API = "/api/board-reminders";
let boardReminders = [];
let boardOnline = false;
let boardRefreshInterval = null;

function switchTab(tab) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  if (tab === "local") {
    document.querySelector(".tab:first-child").classList.add("active");
    document.querySelector(".main").style.display = "block";
    document.getElementById("boardContent").style.display = "none";
    clearInterval(boardRefreshInterval);
  } else {
    document.querySelector(".tab:last-child").classList.add("active");
    document.querySelector(".main").style.display = "none";
    document.getElementById("boardContent").style.display = "block";
    var sbDiv = document.getElementById("stopBtnContainer");
    if (!sbDiv) {
      sbDiv = document.createElement("div");
      sbDiv.id = "stopBtnContainer";
      var btn = document.createElement("button");
      btn.id = "stopPlaybackBtn";
      btn.className = "stop-btn";
      btn.onclick = stopBoardPlayback;
      btn.textContent = "\u5173\u95ed\u5587\u53ed";
      sbDiv.appendChild(btn);
      document.getElementById("boardContent").insertBefore(sbDiv, document.getElementById("boardContent").firstChild);
    }
    loadBoardStatus();
    loadBoardReminders();
    loadBoardPresence();
    clearInterval(boardRefreshInterval);
    boardRefreshInterval = setInterval(function() { loadBoardStatus(); loadBoardReminders(); loadBoardPresence(); }, 5000);
  }
}

async function loadBoardStatus() {
  try {
    const resp = await fetch(BOARD_API + "/status");
    const data = await resp.json();
    boardOnline = data.online || false;
    updateBoardStatusUI(data);
  } catch (e) {
    boardOnline = false;
    document.getElementById("boardStatusText").textContent = "离线";
    document.getElementById("boardStatusDot").className = "board-status-dot off";
    document.getElementById("boardReminderCount").textContent = "";
  }
}

function updateBoardStatusUI(data) {
  const dot = document.getElementById("boardStatusDot");
  const text = document.getElementById("boardStatusText");
  const count = document.getElementById("boardReminderCount");
  if (data.online) {
    dot.className = "board-status-dot on";
    text.textContent = "在线 (" + data.host + ")";
    /* count from loadBoardReminders() */
  } else {
    dot.className = "board-status-dot off";
    text.textContent = "离线";
    count.textContent = "";
  }
}

async function loadBoardReminders() {
  try {
    const resp = await fetch(BOARD_API);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    boardReminders = await resp.json();
    renderBoardReminders();
    var cnt=document.getElementById("boardReminderCount");if(cnt)cnt.textContent="已收到 "+boardReminders.length+" 条提醒";
  } catch (e) {
    console.error("Board load error:", e);
  }
}

function getBoardStatusLabel(status) {
  var labels = {
    "pending": "⏳ 待下发",
    "sent": "📨 已下发",
    "executing": "🔄 执行中",
    "completed": "✅ 已完成",
    "failed": "❌ 失败",
    "cancelled": "🚫 已取消",
    "received": "✅ 已接收",
    "delayed": "🔄 执行中",
    "timeout": "❌ 失败",
    "played": "✅ 已完成",
    "triggered": "✅ 已完成"
  };
  return labels[status] || status;
}

function renderBoardReminders() {
  const grid = document.getElementById("boardReminderGrid");
  if (!boardReminders || boardReminders.length === 0) {
    grid.innerHTML = '<div class="empty-state"><div class="big-icon">🖥️</div><h2>板子提醒</h2><p>板子上暂无提醒事项</p></div>';
    return;
  }
  let html = "";
  for (const r of boardReminders) { try {
    const cid = r.command_id || r.id || "";
    const title = r.title || r.content || "";
    const time = r.reminder_time ? String(r.reminder_time).replace("T", " ") : "-";
    const recv = r.received_at ? String(r.received_at).replace("T", " ").substring(0, 16) : "-";
    const fpath = r.file_path || "";
    const status = r.status || "received";
    html += '<div class="reminder-card">';
    html += '<div class="time-block"><div class="time">' + (time.split(" ")[1] || time) + '</div><div class="date">' + (time.split(" ")[0] || "") + '</div></div>';
    html += '<div class="content"><div class="title">' + escapeHtml(title) + '</div>';
    var rpt = r.repeatType || r.repeat_type || "";
    if (rpt) { html += '<div class="desc">🔄 ' + escapeHtml(rpt) + '</div>'; }
    html += '<div class="desc">收到时间: ' + recv + '</div>';
    html += '<div class="desc file-path">文件位置: ' + escapeHtml(fpath || "未知") + '</div></div>';
    html += '<span class="status-badge ' + status + '">' + getBoardStatusLabel(status) + '</span>';
    html += '<div class="actions">';
    html += '<button class="btn-icon play-btn" onclick="playBoardReminder(\x27' + cid + '\x27)" title="试听">🔊</button>';
    html += '<button class="btn-icon delete-btn" onclick="deleteBoardReminder(\x27' + cid + '\x27)" title="删除">🗑️</button>';
    html += '</div></div>'; } catch(e) { console.error("Render err:", e, r); }
  }
  grid.innerHTML = html;
}

async function playBoardReminder(cmdId) {
  if (!cmdId) return;
  try {
    document.getElementById("nowPlaying").classList.add("active");
    const resp = await fetch(BOARD_API + "/" + cmdId + "/play", { method: "POST" });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert("播放失败: " + (err.detail || ""));
    }
    setTimeout(function() { document.getElementById("nowPlaying").classList.remove("active"); }, 5000);
  } catch (e) {
    alert("播放失败: " + e.message);
    document.getElementById("nowPlaying").classList.remove("active");
  }
}

async function stopBoardPlayback() {
  try {
    const resp = await fetch(BOARD_API + '/stop', { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      const btn = document.getElementById('stopPlaybackBtn');
      if (btn) { btn.textContent = '🔇 已停止'; setTimeout(function() { btn.textContent = '🔊 关闭喇叭'; }, 3000); }
    }
  } catch(e) { console.error('Stop error:', e); }
}

async function deleteBoardReminder(cmdId) {
  if (!cmdId || !confirm("确定要删除这个提醒吗？")) return;
  try {
    const resp = await fetch(BOARD_API + "/" + cmdId, { method: "DELETE" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    await loadBoardReminders();
    await loadBoardStatus();
  } catch (e) {
    alert("删除失败: " + e.message);
  }
}

// Clock
function updateClock() {
  var n = new Date();
  var y = n.getFullYear();
  var mo = String(n.getMonth() + 1).padStart(2, "0");
  var d = String(n.getDate()).padStart(2, "0");
  var h = String(n.getHours()).padStart(2, "0");
  var mi = String(n.getMinutes()).padStart(2, "0");
  var s = String(n.getSeconds()).padStart(2, "0");
  document.getElementById("clockDisplay").textContent = y + "-" + mo + "-" + d + " " + h + ":" + mi + ":" + s;
}
setInterval(updateClock, 1000);
updateClock();

// Presence
async function loadBoardPresence() {
  try {
    const resp = await fetch("/api/board-reminders/presence");
    const data = await resp.json();
    updatePresenceUI(data.present !== false);
  } catch(e) {}
}
function updatePresenceUI(present) {
  var btn = document.getElementById("presenceToggle");
  if (!btn) return;
  if (present) {
    btn.textContent = "👤 有人";
    btn.className = "presence-toggle on";
  } else {
    btn.textContent = "🚫 没人";
    btn.className = "presence-toggle off";
  }
}
async function togglePresence() {
  var btn = document.getElementById("presenceToggle");
  if (!btn) return;
  var isPresent = btn.classList.contains("off");
  try {
    await fetch("/api/board-reminders/presence", { method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({present: isPresent}) });
    updatePresenceUI(isPresent);
  } catch(e) {}
}