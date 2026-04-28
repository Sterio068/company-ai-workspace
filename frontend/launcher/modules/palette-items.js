/**
 * Command palette data source.
 *
 * Keep this module pure-ish: it builds commands from config + current project cache,
 * while callers inject the actions that mutate app state.
 */
import { AI_PROVIDERS, CORE_AGENTS, SKILLS, WORKSPACES, agentRoleName } from "./config.js";
import { Projects } from "./projects.js";
import { design } from "./design.js";

const VIEW_ITEMS = [
  ["dashboard", "🏠 首頁", "⌘0"],
  ["projects", "◎ 工作包", "⌘P"],
  ["skills", "📚 技能庫", "⌘L"],
  ["accounting", "💰 會計", "⌘A"],
  ["tenders", "📢 標案", "⌘T"],
  ["crm", "💼 商機", "⌘I"],
  ["workflows", "↳ 工作流程", "⌘W"],
  ["knowledge", "📚 知識庫", ""],
  ["notebooklm", "▣ NotebookLM", ""],
  ["admin", "📊 管理", "⌘M"],
];

export function buildPaletteItems(actions = {}) {
  const {
    showView,
    openAgent,
    openWorkspace,
    editProject,
    setAIProvider,
  } = actions;

  const items = VIEW_ITEMS.map(([view, label, hint]) => ({
    icon: "",
    label,
    hint,
    action: () => showView?.(view),
  }));

  WORKSPACES.forEach(ws => {
    items.push({
      icon: ws.icon,
      label: `工作區 · ${ws.fullName}`,
      hint: ws.shortcut,
      action: () => openWorkspace?.(ws.id),
    });
  });

  CORE_AGENTS.forEach(agent => {
    items.push({
      icon: agent.emoji,
      label: `角色 · ${agentRoleName(agent)}`,
      hint: agent.model,
      action: () => openAgent?.(agent.num),
    });
  });

  Object.values(AI_PROVIDERS).forEach(provider => {
    items.push({
      icon: "⚙️",
      label: `AI 引擎 · 切換到 ${provider.label}`,
      hint: provider.badge,
      action: () => setAIProvider?.(provider.id),
    });
  });

  Projects.load().forEach(project => {
    items.push({
      icon: "📁",
      label: `工作包 · ${project.name}`,
      hint: project.client || "",
      action: () => editProject?.(project.id || project._id),
    });
  });

  SKILLS.forEach(skill => {
    items.push({
      icon: "📚",
      label: `技能 · ${skill.name}`,
      hint: skill.ws,
      action: () => showView?.("skills"),
    });
  });

  items.push({
    icon: "🎨",
    label: "生圖 · Fal.ai Recraft v3(每次 3 張挑方向)",
    hint: "/design",
    action: () => design.openPromptModal(),
  });

  return items;
}
