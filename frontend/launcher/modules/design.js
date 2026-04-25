/**
 * Design helper · V1.1-SPEC §A · 前端 Fal.ai 生圖閉環
 * =====================================
 * 負責:
 *   · POST /design/recraft(與後端合意 num_images=3)
 *   · pending 時接 GET /design/recraft/status/{job_id} polling
 *   · 回 Promise<{status, images[], friendly_message}>
 *
 * 使用者:
 *   · 設計助手 chat modal 或按鈕 → await design.generate({prompt, image_size})
 *   · 回來的 images 可直接 <img src={url}> 嵌入
 */
import { authFetch } from "./auth.js";

const BASE = "/api-accounting";
const POLL_INTERVAL_MS = 1500;
const POLL_MAX_ROUNDS = 40;  // ~60 秒 · Fal 慢時大約需要

export const design = {
  /**
   * 生圖閉環 · 回 Promise
   * @param {object} opts · {prompt, image_size?, style?, project_id?, onProgress?}
   * @returns {Promise<{status, images, friendly_message, job_id?}>}
   */
  async generate(opts) {
    const { prompt, image_size = "square_hd", style = "realistic_image",
            project_id = null, regenerate_of = null, onProgress } = opts;

    if (!prompt || prompt.length < 4) {
      return { status: "rejected", images: [],
               friendly_message: "描述太短 · 請至少 4 個字" };
    }

    onProgress?.({ phase: "submit", message: "送出生圖需求…" });

    // ========== Phase 1 · POST /design/recraft ==========
    let firstResponse;
    try {
      const r = await authFetch(`${BASE}/design/recraft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, image_size, style, project_id, regenerate_of }),
      });
      if (r.status === 503) {
        const body = await r.json().catch(() => ({}));
        return {
          status: "unconfigured",
          images: [],
          friendly_message: body.detail?.friendly_message
            || "設計助手尚未啟用 · 請管理員設定生圖服務金鑰",
        };
      }
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        return {
          status: "error",
          images: [],
          friendly_message: body.detail?.friendly_message
            || `設計服務錯誤 (HTTP ${r.status})`,
        };
      }
      firstResponse = await r.json();
    } catch (e) {
      return {
        status: "error",
        images: [],
        friendly_message: "網路錯誤 · 請稍後重試",
      };
    }

    // ========== Phase 2 · 檢查 done / rejected / pending ==========
    if (firstResponse.status === "done") {
      onProgress?.({ phase: "done", message: "完成" });
      return {
        status: "done",
        images: firstResponse.images || [],
        friendly_message: null,
        job_id: firstResponse.job_id,
      };
    }
    if (firstResponse.status === "rejected") {
      return {
        status: "rejected",
        images: [],
        friendly_message: firstResponse.friendly_message,
      };
    }
    if (firstResponse.status !== "pending" || !firstResponse.job_id) {
      return {
        status: "error",
        images: [],
        friendly_message: firstResponse.friendly_message || "非預期的回應",
      };
    }

    // ========== Phase 3 · Poll 直到 completed 或超時 ==========
    const jobId = firstResponse.job_id;
    onProgress?.({
      phase: "pending",
      message: firstResponse.friendly_message || "生圖中 · 請稍候…",
      job_id: jobId,
    });

    for (let round = 1; round <= POLL_MAX_ROUNDS; round++) {
      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
      try {
        const r = await authFetch(`${BASE}/design/recraft/status/${jobId}`);
        if (!r.ok) continue;  // 單次 poll 失敗不致命
        const body = await r.json();
        if (body.status === "done") {
          onProgress?.({ phase: "done", message: "完成" });
          return {
            status: "done",
            images: body.images || [],
            friendly_message: null,
            job_id: jobId,
          };
        }
        // 仍 pending · onProgress 更新等待時間
        const elapsedSec = Math.round((round * POLL_INTERVAL_MS) / 1000);
        onProgress?.({
          phase: "pending",
          message: `生圖中 · 已等 ${elapsedSec} 秒`,
          job_id: jobId,
          round,
        });
      } catch {
        // 單次失敗不致命 · 繼續 poll
      }
    }

    // ========== Phase 4 · 超時 ==========
    return {
      status: "timeout",
      images: [],
      friendly_message: "生圖時間超過 60 秒 · Fal 隊伍壅塞 · 請稍後在「歷史」查看",
      job_id: jobId,
    };
  },

  /**
   * 最小 UI · 開 modal 顯示 prompt 輸入 · 送出 · pending 進度 · 完成圖片網格
   * 給 Admin 試用 / chat 模組 embed 都適用
   */
  async openPromptModal() {
    const { modal } = await import("./modal.js");
    const { toast } = await import("./toast.js");
    const formHtml = `
      <form id="design-form" class="modal2-form">
        <label>
          <span>描述(越具體越好 · 避免真人寫實 / 政府標誌)</span>
          <textarea name="prompt" rows="4" required minlength="4"
            placeholder="例:中秋節品牌主視覺 · 橘黃色調 · 扁平幾何 · 月亮與兔子剪影"></textarea>
        </label>
        <div class="field-row">
          <label>
            <span>尺寸</span>
            <select name="image_size">
              <option value="square_hd">高畫質方形</option>
              <option value="portrait_16_9">直式 16:9</option>
              <option value="landscape_16_9">橫式 16:9</option>
            </select>
          </label>
          <label>
            <span>風格</span>
            <select name="style">
              <option value="realistic_image">寫實</option>
              <option value="digital_illustration">數位插畫</option>
              <option value="vector_illustration">向量插畫</option>
            </select>
          </label>
        </div>
        <div id="design-progress" class="hint" style="margin-top:8px; min-height:20px"></div>
        <div id="design-results" style="margin-top:12px; display:grid; grid-template-columns:repeat(3,1fr); gap:8px"></div>
      </form>`;
    return modal.openForm({
      title: "🎨 生圖(每次 3 張 · 挑方向)",
      bodyHTML: formHtml,
      primary: "生成",
      onSubmit: async () => {
        const f = document.getElementById("design-form");
        if (!f.reportValidity()) return false;
        const prompt = f.prompt.value.trim();
        const image_size = f.image_size.value;
        const style = f.style.value;
        const progressEl = document.getElementById("design-progress");
        const resultsEl = document.getElementById("design-results");
        resultsEl.innerHTML = "";

        const result = await design.generate({
          prompt, image_size, style,
          onProgress: (p) => {
            if (progressEl) progressEl.textContent = p.message || "";
          },
        });

        if (result.status === "done") {
          resultsEl.innerHTML = result.images.map(img => `
            <a href="${img.url}" target="_blank" style="display:block">
              <img src="${img.url}" style="width:100%; border-radius:8px" alt="生成圖">
            </a>
          `).join("");
          progressEl.textContent = `✓ 完成 · ${result.images.length} 張`;
          toast.success("生圖完成");
        } else {
          progressEl.textContent = result.friendly_message || "失敗";
          toast.error(result.friendly_message || "生圖失敗");
        }
        return false;  // 不關 modal · 讓使用者看圖 / 重生
      },
    });
  },
};
