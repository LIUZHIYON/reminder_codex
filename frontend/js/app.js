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
    loadBoardStatus();
    loadBoardReminders();
    clearInterval(boardRefreshInterval);
    boardRefreshInterval = setInterval(function() { loadBoardStatus(); loadBoardReminders(); }, 5000);
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
    document.getElementById("boardStatusText").textContent = "\u79bb\u7ebf";
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
    text.textContent = "\u5728\u7ebf (" + data.host + ")";
    count.textContent = "\u5df2\u6536\u5230 " + (data.reminder_count || 0) + " \u6761\u63d0\u9192";
  } else {
    dot.className = "board-status-dot off";
    text.textContent = "\u79bb\u7ebf";
    count.textContent = "";
  }
}

async function loadBoardReminders() {
  try {
    const resp = await fetch(BOARD_API);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    boardReminders = await resp.json();
    renderBoardReminders();
  } catch (e) {
    console.error("Board load error:", e);
  }
}

function renderBoardReminders() {
  const grid = document.getElementById("boardReminderGrid");
  if (!boardReminders || boardReminders.length === 0) {
    grid.innerHTML = '<div class="empty-state"><div class="big-icon">\U0001f5a5\ufe0f</div><h2>\u677f\u5b50\u63d0\u9192</h2><p>\u677f\u5b50\u4e0a\u66ab\u65e0\u63d0\u9192\u4e8b\u9879</p></div>';
    return;
  }
  let html = "";
  for (const r of boardReminders) {
    const cid = r.command_id || r.id || "";
    const title = r.title || r.content || "";
    const time = r.reminder_time ? new Date(r.reminder_time).toLocaleString("zh-CN") : "-";
    const recv = r.received_at ? new Date(r.received_at).toLocaleString("zh-CN") : "-";
    const fpath = r.file_path || "";
    const status = r.status || "received";
    html += '<div class="reminder-card">';
    html += '<div class="time-block"><div class="time">' + (time.split(" ")[1] || time) + '</div><div class="date">' + (time.split(" ")[0] || "") + '</div></div>';
    html += '<div class="content"><div class="title">' + escapeHtml(title) + '</div>';
    html += '<div class="desc">\u6536\u5230\u65f6\u95f4: ' + recv + '</div>';
    html += '<div class="desc file-path">\u6587\u4ef6\u4f4d\u7f6e: ' + escapeHtml(fpath || "\u672a\u77e5") + '</div></div>';
    html += '<span class="status-badge received">\u2714 \u5df2\u63a5\u6536</span>';
    html += '<div class="actions">';
    html += '<button class="btn-icon play-btn" onclick="playBoardReminder(\x27' + cid + '\x27)" title="\u8bd5\u542c">\U0001f50a</button>';
    html += '<button class="btn-icon delete-btn" onclick="deleteBoardReminder(\x27' + cid + '\x27)" title="\u5220\u9664">\U0001f5d1\ufe0f</button>';
    html += '</div></div>';
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
      alert("\u64ad\u653e\u5931\u8d25: " + (err.detail || ""));
    }
    setTimeout(function() { document.getElementById("nowPlaying").classList.remove("active"); }, 5000);
  } catch (e) {
    alert("\u64ad\u653e\u5931\u8d25: " + e.message);
    document.getElementById("nowPlaying").classList.remove("active");
  }
}

async function deleteBoardReminder(cmdId) {
  if (!cmdId || !confirm("\u786e\u5b9a\u8981\u5220\u9664\u8fd9\u4e2a\u63d0\u9192\u5417\uff1f")) return;
  try {
    const resp = await fetch(BOARD_API + "/" + cmdId, { method: "DELETE" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    await loadBoardReminders();
    await loadBoardStatus();
  } catch (e) {
    alert("\u5220\u9664\u5931\u8d25: " + e.message);
  }
}
