/**
 * Launcher · 共用 utility
 * ES module · 無狀態 · 全 pure functions
 */

export async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, { credentials: "include", ...opts });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/**
 * 共用剪貼簿 utility · 集中所有 navigator.clipboard 呼叫
 * 用法:
 *   await copyToClipboard("xxx");                              // 純複製
 *   await copyToClipboard(text, btnEl, { okText: "✓ 已複製" }) // 複製 + 按鈕飛字反饋
 *
 * 雙路徑:
 *   - 主路徑:navigator.clipboard.writeText(secure context · HTTPS / localhost OK)
 *   - 降級:document.execCommand('copy')(LAN HTTP / 舊版 Safari · 不需 secure context)
 *
 * @param {string} text 要複製的字串
 * @param {HTMLElement|null} btn 反饋的按鈕(可選)· 會暫改 textContent + .ok class · 1.5s 後還原
 * @param {{ okText?: string, errorText?: string, durationMs?: number }} [opts]
 * @returns {Promise<boolean>} 成功 true · 失敗 false(已 toast.error)
 */
export async function copyToClipboard(text, btn = null, opts = {}) {
  const okText = opts.okText || "✓ 已複製";
  const errorText = opts.errorText || "複製失敗 · 請手動選取";
  const duration = opts.durationMs ?? 1500;
  const value = String(text ?? "");

  const flashFeedback = () => {
    if (!btn) return;
    const orig = btn.textContent;
    btn.textContent = okText;
    btn.classList.add("ok");
    setTimeout(() => {
      btn.textContent = orig;
      btn.classList.remove("ok");
    }, duration);
  };

  // 主路徑 · 需 secure context (HTTPS / localhost)
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      flashFeedback();
      return true;
    } catch {
      // fall through 到 execCommand
    }
  }

  // 降級 · LAN HTTP (192.168.x.x) / 舊版 Safari · 用隱藏 textarea + execCommand
  try {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) {
      flashFeedback();
      return true;
    }
  } catch {
    // 再失敗就降級到 toast
  }

  if (typeof window !== "undefined" && window.toast?.error) {
    window.toast.error(errorText);
  }
  return false;
}

export function formatDate(d) {
  // v1.3 P1#10 · 簡化:2026.04.23 週三
  const wk = ["日", "一", "二", "三", "四", "五", "六"];
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}.${m}.${day} 週${wk[d.getDay()]}`;
}

export function formatDateShort(iso) {
  // v1.3 P1#10 · 列表 / chip 用 · 簡短「4/23 14:30」
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export function greetingFor(hour) {
  if (hour < 6)  return "凌晨好";
  if (hour < 12) return "早安";
  if (hour < 14) return "午安";
  if (hour < 18) return "下午好";
  return "晚上好";
}

export function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diffMs / 60000);
  if (m < 1)  return "剛剛";
  if (m < 60) return `${m} 分前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 時前`;
  const d = Math.floor(h / 24);
  return `${d} 天前`;
}

export function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function formatMoney(n) {
  if (!n || isNaN(n)) return "—";
  return "NT$ " + Number(n).toLocaleString("en-US");
}

export function skeletonCards(count = 3) {
  return Array(count).fill(0).map(() => `
    <div class="skeleton-card">
      <div class="skeleton skeleton-line md"></div>
      <div class="skeleton skeleton-line sm"></div>
      <div class="skeleton skeleton-line"></div>
    </div>
  `).join("");
}

const UI_TEXT_REPLACEMENTS = [
  [/Strict Validation Response/g, "嚴格驗收回覆"],
  [/Legacy Assistant Cleanup Test/g, "舊版助手清理測試"],
  [/Reinstallation Seventh Round Normal/g, "重新安裝第七輪正常"],
  [/drawer smoke/g, "抽屜流程測試"],
  [/\br13-test\b/g, "商機測試"],
  [/\be2e\b/g, "測試資料源"],
  [/\bunknown\b/g, "未分類助手"],
  [/\bOpenAI\b/g, "主力引擎"],
  [/\bClaude\b/g, "備援引擎"],
  [/\bAnthropic\b/g, "備援模型服務"],
  [/\bADMIN\b/g, "管理員"],
  [/\bUSER\b/g, "一般同仁"],
  [/\bchengfu_permissions\b/g, "權限設定"],
  [/\bMongoDB\b/g, "資料庫"],
  [/\bMongo\b/g, "資料庫"],
  [/\bMeilisearch\b/g, "全文搜尋服務"],
  [/\bNAS\b/g, "網路儲存"],
  [/\bUSB\b/g, "隨身碟"],
  [/\bPlaybook\b/g, "作業劇本"],
  [/\bAP Style\b/g, "新聞寫作格式"],
  [/\bhook\b/gi, "開場鉤子"],
  [/\bchecklist\b/gi, "檢查清單"],
  [/\bPDPA\b/g, "個資法"],
  [/\bSlash\b/g, "快速命令"],
  [/\bUTC\b/g, "國際標準時間"],
  [/\bTTL\b/g, "保存期限"],
  [/\bKPI\b/g, "成效指標"],
  [/\bcron\b/gi, "排程服務"],
  [/\bPDF\b/g, "文件"],
  [/\bAPI\b/g, "介接"],
  [/\bSTT\b/g, "語音轉文字"],
  [/\bWhisper\b/g, "語音轉文字"],
  [/\bgpt-image-2\b/g, "高品質生圖模型"],
  [/\bApp Password\b/g, "應用程式密碼"],
  [/\bSMTP\b/g, "寄信服務"],
  [/\bcookie\b/g, "登入憑證"],
  [/\bLibreChat\b/g, "對話系統"],
  [/\bschema\b/gi, "資料結構"],
  [/\btimeout\b/gi, "逾時"],
  [/\btoken\b/gi, "權杖"],
  [/\btokens\b/gi, "權杖"],
  [/\bProvider\b/g, "服務商"],
  [/\bprovider\b/g, "服務商"],
  [/\bPM\b/g, "專案窗口"],
  [/\bDB\b/g, "資料庫"],
  [/\bCRUD\b/g, "增查改刪"],
  [/\bReindex\b/g, "重新索引"],
  [/\breindex\b/g, "重新索引"],
  [/\bindex\b/g, "索引"],
  [/\bDay 0\b/g, "上線第一天"],
  [/\bTier\b/g, "級別"],
  [/\bUSD\b/g, "美金"],
  [/\.env/g, "環境設定"],
  [/\bANTHROPIC_API_KEY\b/g, "備援模型服務金鑰"],
  [/\bOPENAI_API_KEY\b/g, "主力模型服務金鑰"],
  [/\bFAL_API_KEY\b/g, "生圖服務金鑰"],
  [/\bIMAGE_PROVIDER\b/g, "生圖服務商設定"],
  [/\bEMAIL_USERNAME\b/g, "寄信帳號"],
  [/\bEMAIL_PASSWORD\b/g, "寄信密碼"],
  [/\bJWT_REFRESH_SECRET\b/g, "登入安全密鑰"],
  [/\bECC_INTERNAL_TOKEN\b/g, "內部通行權杖"],
  [/\bMEILI_MASTER_KEY\b/g, "全文搜尋主密鑰"],
  [/SMTP Username/g, "寄信帳號"],
  [/SMTP Password/g, "寄信密碼"],
  [/JWT Refresh Secret/g, "登入安全密鑰"],
  [/Meilisearch Master Key/g, "全文搜尋主密鑰"],
  [/\bclaude-sonnet-4-6\b/g, "備援模型"],
  [/\bgpt-5\.4\b/g, "主力模型"],
  [/\bTENDER_MONITOR_KEYWORDS\b/g, "標案關鍵字設定"],
  [/scripts\/tender-monitor\.py/g, "標案監測排程"],
  [/DEPLOY\.md Phase 4\.5/g, "交付手冊的排程章節"],
  [/\bAdmin\b/g, "管理員"],
  [/\badmin\b/g, "管理員"],
  [/\bWorkspace\b/g, "工作區"],
  [/\bworkspace\b/g, "工作區"],
  [/\bAgent\b/g, "助手"],
  [/\bAgents\b/g, "助手"],
  [/\bProject\b/g, "專案"],
  [/\bProjects\b/g, "專案"],
  [/\bHandoff\b/g, "交棒卡"],
  [/\bDashboard\b/g, "首頁"],
  [/\bdashboard\b/g, "首頁"],
  [/\bBrief\b/g, "需求單"],
  [/\bEmail\b/g, "電子郵件"],
  [/\bemail\b/g, "電子郵件"],
  [/\bURL\b/g, "網路連結"],
  [/\bPII\b/g, "個人資料"],
  [/\bL1\b/g, "第一級"],
  [/\bL2\b/g, "第二級"],
  [/\bL3\b/g, "第三級"],
  [/\bLevel\b/g, "級別"],
  [/\bCSV\b/g, "表格"],
  [/\bPWA\b/g, "行動版網頁"],
  [/\bmock\b/g, "練習模式"],
  [/\bstatus\b/g, "狀態"],
  [/\bpending\b/g, "處理中"],
  [/\bdone\b/g, "完成"],
  [/\bfailed\b/g, "失敗"],
  [/\bactive\b/g, "啟用"],
  [/\bclosed\b/g, "結案"],
  [/\baudio note\b/gi, "語音備註"],
  [/\bprompt\b/gi, "指令"],
  [/\bquota\b/gi, "用量額度"],
  [/\baudit\b/gi, "稽核紀錄"],
];

export function localizeVisibleText(root = document.body) {
  if (!root || typeof document === "undefined") return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      const tag = parent.tagName;
      if (["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "SELECT"].includes(tag)) return NodeFilter.FILTER_REJECT;
      if (!/[A-Za-z]/.test(node.nodeValue || "")) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(node => {
    let text = node.nodeValue;
    UI_TEXT_REPLACEMENTS.forEach(([pattern, replacement]) => {
      text = text.replace(pattern, replacement);
    });
    node.nodeValue = text;
  });
}
