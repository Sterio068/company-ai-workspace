/**
 * Help State · 教學狀態 · 角色 + 進度 · localStorage
 * ==========================================================
 * 對應 vNext B + D · 角色化 + 進度追蹤
 *
 * 角色 5 + 1 unknown:
 *   boss / pm / design / pr / account / unknown
 *
 * 每個角色有「優先學的 6-8 個 task」
 * 進度 = 完成 task 數 / 角色 task 總數
 */

const ROLE_KEY = "chengfu-help-role";
const PROGRESS_KEY = "chengfu-help-progress";  // { task_id: timestamp }
const TIPS_SEEN_KEY = "chengfu-help-tips-seen";  // { view_id: timestamp }

export const ROLES = {
  boss: {
    label: "老闆 / 決策者",
    icon: "👔",
    desc: "管全公司 · 看儀表板 · 找標案 · 算帳",
    priority_tasks: [
      "ftue-01-first-task",
      "ftue-02-handoff-card",
      "tutorial-dashboard-monthly-cost",
      "tutorial-dashboard-budget-alert",
      "tutorial-tender-monitor",
      "tutorial-crm-import-tender",
      "tutorial-admin-add-user",
      "tutorial-pdpa-export",
    ],
  },
  pm: {
    label: "PM / 專案經理",
    icon: "🎯",
    desc: "管多案 · 整理客戶需求 · 分派 · 收稿 · 交棒",
    priority_tasks: [
      "ftue-01-first-task",
      "ftue-02-handoff-card",
      "ftue-03-meeting-summary",
      "tutorial-attach-pdf",
      "tutorial-handoff-copy-line",
      "tutorial-tender-go-no-go",
      "tutorial-crm-followup",
      "tutorial-site-brief-copy",
      "tutorial-workspace-tender",
      "tutorial-workspace-event",
    ],
  },
  design: {
    label: "設計師",
    icon: "🎨",
    desc: "看交棒卡 · 拿 brief · 用 AI 發想 · 多渠道適配",
    priority_tasks: [
      "ftue-01-first-task",
      "tutorial-design-kv-brainstorm",
      "tutorial-design-brief-from-handoff",
      "tutorial-design-ai-image",
      "tutorial-multichannel-resize",
      "tutorial-handoff-receive",
    ],
  },
  pr: {
    label: "公關 / 媒體",
    icon: "📣",
    desc: "寫新聞稿 · 經營媒體名單 · 發稿追蹤",
    priority_tasks: [
      "ftue-01-first-task",
      "tutorial-press-draft",
      "tutorial-media-recommend",
      "tutorial-media-pitch-track",
      "tutorial-social-schedule",
      "tutorial-meeting-summary",
      "tutorial-crm-followup",
    ],
  },
  account: {
    label: "會計 / 財務",
    icon: "💰",
    desc: "開發票 · 算毛利 · 看月帳",
    priority_tasks: [
      "ftue-01-first-task",
      "tutorial-accounting-invoice",
      "tutorial-accounting-quote",
      "tutorial-accounting-transaction",
      "tutorial-accounting-pnl",
      "tutorial-budget-alert",
    ],
  },
  unknown: {
    label: "尚未選 · 全功能瀏覽",
    icon: "❓",
    desc: "看完整 13 份手冊 · 自己挑",
    priority_tasks: [],  // 空 = 不算進度 · 全展示
  },
};

/** 取當前角色 · 預設 unknown */
export function getRole() {
  const r = localStorage.getItem(ROLE_KEY);
  return ROLES[r] ? r : "unknown";
}

/** 設定角色 · 觸發 'help-role-changed' event */
export function setRole(role) {
  if (!ROLES[role]) return false;
  localStorage.setItem(ROLE_KEY, role);
  document.dispatchEvent(new CustomEvent("help-role-changed", { detail: { role } }));
  return true;
}

/** 取已完成 task ids set */
export function getProgress() {
  try {
    return JSON.parse(localStorage.getItem(PROGRESS_KEY) || "{}");
  } catch {
    return {};
  }
}

/** 標記 task 完成 · 觸發 'help-progress-changed' event */
export function markTaskDone(taskId) {
  if (!taskId) return;
  const p = getProgress();
  if (p[taskId]) return;  // 已標 · skip
  p[taskId] = new Date().toISOString();
  localStorage.setItem(PROGRESS_KEY, JSON.stringify(p));
  document.dispatchEvent(new CustomEvent("help-progress-changed", { detail: { taskId } }));
}

/** 重設角色進度(testing / 用戶要求重來)*/
export function resetProgress() {
  localStorage.removeItem(PROGRESS_KEY);
  document.dispatchEvent(new CustomEvent("help-progress-changed", { detail: { reset: true } }));
}

/** 角色進度 · 回 { done, total, percent } */
export function getRoleProgress(role = null) {
  const r = role || getRole();
  const meta = ROLES[r];
  if (!meta || !meta.priority_tasks.length) {
    return { done: 0, total: 0, percent: 0 };
  }
  const progress = getProgress();
  const done = meta.priority_tasks.filter(t => progress[t]).length;
  const total = meta.priority_tasks.length;
  return {
    done,
    total,
    percent: Math.round((done / total) * 100),
  };
}

/** view 第一次進 · 是否該 show inline tip */
export function shouldShowTip(viewId) {
  try {
    const seen = JSON.parse(localStorage.getItem(TIPS_SEEN_KEY) || "{}");
    return !seen[viewId];
  } catch {
    return true;
  }
}

/** 標記 view tip 已看過 */
export function markTipSeen(viewId) {
  try {
    const seen = JSON.parse(localStorage.getItem(TIPS_SEEN_KEY) || "{}");
    seen[viewId] = new Date().toISOString();
    localStorage.setItem(TIPS_SEEN_KEY, JSON.stringify(seen));
  } catch {}
}

/** 重設所有 tip(讓 user 重新看一次)*/
export function resetTipsSeen() {
  localStorage.removeItem(TIPS_SEEN_KEY);
}
