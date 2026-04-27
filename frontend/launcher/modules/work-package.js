import { formatMoney } from "./util.js";

export function projectUpdatedAt(project) {
  return project?.updatedAt || project?.updated_at || project?.createdAt || project?.created_at || "";
}

export function projectUpdatedTs(project) {
  const timestamp = Date.parse(projectUpdatedAt(project));
  return Number.isFinite(timestamp) ? timestamp : 0;
}

export function projectColor(name = "") {
  const colors = ["#D14B43", "#D8851E", "#5AB174", "#3F86C9", "#8C5CB1", "#D14B6F"];
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) % colors.length;
  }
  return colors[hash];
}

export function sortProjects(list = []) {
  return [...list].sort((a, b) => {
    const statusWeight = (project) => (project.status === "closed" ? 1 : 0);
    const statusDiff = statusWeight(a) - statusWeight(b);
    if (statusDiff !== 0) return statusDiff;
    const ad = a.deadline ? new Date(a.deadline).getTime() : Number.MAX_SAFE_INTEGER;
    const bd = b.deadline ? new Date(b.deadline).getTime() : Number.MAX_SAFE_INTEGER;
    if (ad !== bd) return ad - bd;
    return projectUpdatedTs(b) - projectUpdatedTs(a);
  });
}

export function filterProjects(projects = [], { filter = "all", search = "" } = {}) {
  let list = projects;
  if (filter !== "all") list = list.filter(project => project.status === filter);
  const query = search.trim().toLowerCase();
  if (query) {
    list = list.filter(project => [
      project.name,
      project.client,
      project.description,
      project.next_owner,
      ...(project.collaborators || []),
    ].filter(Boolean).join(" ").toLowerCase().includes(query));
  }
  return sortProjects(list);
}

export function selectDefaultProjectId({ activeProjectId, filteredProjects = [], allProjects = [] } = {}) {
  if (activeProjectId && filteredProjects.some(project =>
    project.id === activeProjectId || project._id === activeProjectId
  )) {
    return activeProjectId;
  }
  const active = filteredProjects[0]
    || sortProjects(allProjects.filter(project => project.status !== "closed"))[0]
    || sortProjects(allProjects)[0];
  return active?.id || active?._id || null;
}

export function projectDeadline(project) {
  if (!project?.deadline) return { label: "未設定截止", tone: "muted", days: null };
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const due = new Date(project.deadline);
  due.setHours(0, 0, 0, 0);
  const days = Math.ceil((due.getTime() - now.getTime()) / 86400000);
  if (days < 0) return { label: `已逾期 ${Math.abs(days)} 天`, tone: "danger", days };
  if (days === 0) return { label: "今天截止", tone: "danger", days };
  if (days <= 3) return { label: `${days} 天內截止`, tone: "warn", days };
  return { label: `${days} 天後截止`, tone: "ok", days };
}

export function workReadiness(project) {
  const handoff = project?.handoff || {};
  const checks = [
    ["客戶", project?.client],
    ["期限", project?.deadline],
    ["預算", project?.budget],
    ["工作脈絡", project?.description],
    ["下一棒", project?.next_owner],
    ["協作者", (project?.collaborators || []).length],
    ["交棒目標", handoff.goal],
    ["明確下一步", (handoff.next_actions || []).length],
  ];
  const done = checks.filter(([, value]) => Boolean(value)).length;
  const missing = checks.filter(([, value]) => !value).map(([label]) => label);
  return {
    score: Math.round((done / checks.length) * 100),
    done,
    total: checks.length,
    missing,
  };
}

export function workKind(project) {
  const text = [project?.name, project?.client, project?.description].filter(Boolean).join(" ");
  if (/標案|投標|招標|採購|委託|政府/.test(text)) return { label: "投標型", ws: 1, color: "#D14B43" };
  if (/活動|記者會|說明會|場地|舞台|動線|展覽/.test(text)) return { label: "活動型", ws: 2, color: "#D8851E" };
  if (/設計|視覺|KV|主視覺|素材|海報|banner/i.test(text)) return { label: "設計型", ws: 3, color: "#8C5CB1" };
  if (/新聞|媒體|社群|貼文|公關|email/i.test(text)) return { label: "公關型", ws: 4, color: "#5AB174" };
  return { label: "營運型", ws: 5, color: "#3F86C9" };
}

export function workActionSuggestions(project, readiness, kind, deadline) {
  const handoff = project?.handoff || {};
  const hasAssets = (handoff.asset_refs || []).some(asset => asset.ref || asset.label);
  const hasNext = (handoff.next_actions || []).length > 0;
  const suggestions = [];

  if (readiness.missing.length) {
    suggestions.push({
      kind: "gaps",
      icon: "？",
      title: `先補 ${readiness.missing.length} 個缺口`,
      desc: "把不完整欄位變成可問客戶、同仁或主管的待確認清單。",
      cta: "整理缺口",
    });
  }

  if (deadline.days !== null && deadline.days <= 3) {
    suggestions.push({
      kind: "daily",
      icon: "！",
      title: deadline.days < 0 ? "先救逾期項目" : "今天先守住期限",
      desc: "把工作拆成今日可完成的短任務,標出誰要接、缺什麼素材。",
      cta: "排今日行動",
    });
  }

  if (readiness.score >= 63) {
    suggestions.push({
      kind: "deliverable",
      icon: "稿",
      title: "直接產第一版",
      desc: `依目前脈絡產出${kind.label}成果大綱,並清楚標出假設與待確認處。`,
      cta: "產第一版",
    });
  } else if (!hasNext) {
    suggestions.push({
      kind: "next",
      icon: "拆",
      title: "先拆可執行任務",
      desc: "把模糊工作轉成 3 個下一步,每一步都有負責角色與完成定義。",
      cta: "拆下一步",
    });
  }

  suggestions.push({
    kind: "handoff",
    icon: "交",
    title: "產交棒卡",
    desc: "整理目標、限制、素材、下一棒與待確認問題,方便跨人交接。",
    cta: "產交棒卡",
  });

  suggestions.push(hasAssets ? {
    kind: "playbook",
    icon: "路",
    title: `套用${kind.label}流程`,
    desc: "用對應工作流程補上風險、里程碑與下一個可交辦任務。",
    cta: "套流程",
  } : {
    kind: "assets",
    icon: "材",
    title: "先補素材地圖",
    desc: "列出已知素材、待補素材、建議檔名與資料夾結構。",
    cta: "整理素材",
  });

  const seen = new Set();
  return suggestions.filter(item => {
    if (seen.has(item.kind)) return false;
    seen.add(item.kind);
    return true;
  }).slice(0, 4);
}

export function projectPromptContext(project) {
  const handoff = project?.handoff || {};
  const next = (handoff.next_actions || []).join("\n");
  const assets = (handoff.asset_refs || []).map(asset => asset.ref || asset.label || "").filter(Boolean).join("\n");
  return [
    `工作包:${project?.name || "未命名"}`,
    `客戶:${project?.client || "未設定"}`,
    `預算:${project?.budget ? formatMoney(project.budget) : "未設定"}`,
    `截止日:${project?.deadline || "未設定"}`,
    `下一棒:${project?.next_owner || "未設定"}`,
    `協作者:${(project?.collaborators || []).join(", ") || "未設定"}`,
    `描述:${project?.description || "未設定"}`,
    next ? `既有下一步:\n${next}` : "",
    assets ? `素材來源:\n${assets}` : "",
  ].filter(Boolean).join("\n");
}

export function workHandoffSaveConfig(project, actionKind) {
  const id = project?.id || project?._id;
  if (!id) return null;
  const name = project?.name || "工作包";
  const shortName = name.length > 12 ? `${name.slice(0, 12)}…` : name;
  const map = {
    next:        { target: "next_action", label: "下一步拆解" },
    daily:       { target: "next_action", label: "今日行動清單" },
    gaps:        { target: "asset_ref", label: "待確認缺口清單" },
    assets:      { target: "asset_ref", label: "素材地圖" },
    handoff:     { target: "asset_ref", label: "交棒卡草稿" },
    deliverable: { target: "asset_ref", label: "第一版成果草稿" },
    playbook:    { target: "asset_ref", label: "流程推進草稿" },
  };
  const meta = map[actionKind] || map.next;
  return {
    projectId: id,
    projectName: name,
    target: meta.target,
    label: meta.label,
    cta: `回寫「${shortName}」`,
  };
}
