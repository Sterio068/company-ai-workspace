/**
 * Chat 附件 · 純函數工具 · v1.50 從 chat.js 抽出
 *
 * 只放沒有 this 依賴的純函數,讓 chat.js 變短的同時不增加耦合複雜度。
 * 上傳行為 / DOM render 仍留在 chat.js · 因為與對話狀態強耦合。
 */
import { ATTACHMENT } from "./config.js";

const { MAX_BYTES, SUPPORTED_EXT } = ATTACHMENT;

/**
 * 檢查單一附件 · 返回 { ok, message }
 * @param {File} file
 */
export function validateAttachment(file) {
  if (!file) return { ok: false, message: "檔案讀取失敗" };
  if (file.size > MAX_BYTES) {
    return { ok: false, message: `${file.name} 超過 25MB,請壓縮或分段上傳` };
  }
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  if (!SUPPORTED_EXT.has(ext)) {
    return { ok: false, message: `${file.name} 格式暫不支援` };
  }
  return { ok: true };
}

/**
 * 把使用者訊息與已上傳附件組成最終文字內容
 * @param {string} text
 * @param {Array<{filename?:string,file_id:string}>} uploadedAttachments
 */
export function composeUserMessageSummary(text, uploadedAttachments) {
  if (!uploadedAttachments?.length) return text;
  const list = uploadedAttachments.map(file => `• ${file.filename || file.file_id}`).join("\n");
  return [text || "請閱讀附件並整理重點。", "", "附件:", list].join("\n");
}

/**
 * 比較兩個 File 是否邏輯上相同(用於去重附件)
 */
export function isSameFile(a, b) {
  return a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;
}
