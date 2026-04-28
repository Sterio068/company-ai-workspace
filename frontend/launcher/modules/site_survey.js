/**
 * Site Survey · Feature #7 · 場勘 PWA 前端
 * ==========================================================
 * 流程:
 *   1. 「拍照」按 → input file capture=camera(iPhone Safari 開相機)
 *   2. 連續拍 1-5 張 · 顯示縮圖
 *   3. 「取得 GPS」按 → navigator.geolocation
 *   4. 填地址提示(可選)+ 專案 ID
 *   5. 上傳 → polling status → 顯示 AI 結構化結果
 *   6. 一鍵推到 Handoff
 *
 * iPhone HEIC 限制:
 *   - 後端只接 JPEG/PNG/WebP · HEIC 會被 reject
 *   - 提示 user 到「設定 → 相機 → 格式 → 最相容」
 */
import { authFetch } from "./auth.js";
import { escapeHtml } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";
import { markTaskDone } from "./help-state.js";

const BASE = "/api-accounting";
const MAX_IMAGES = 5;
const MAX_BYTES = 5 * 1024 * 1024;

export const siteSurvey = {
  _images: [],  // [{ file, dataUrl }]
  _gps: null,   // { lat, lng, accuracy }
  _addressHint: "",
  _projectId: "",
  _currentSurveyId: null,
  _pollTimer: null,

  init() {
    this.render();
    this._loadHistory();
  },

  render() {
    const root = document.getElementById("view-site-content");
    if (!root) return;

    const heicWarn = (typeof navigator !== "undefined" && /iPhone|iPad/.test(navigator.userAgent))
      ? `<div class="site-warn">📱 iPhone 可直接上傳 HEIC；若這台主機未安裝 HEIC 轉檔套件,系統會提示改用「最相容」JPEG。</div>`
      : "";

    root.innerHTML = `
      ${heicWarn}
      <section class="module-command-hero site-command-hero">
        <div>
          <span class="ops-command-kicker">場勘工作台</span>
          <h2>現場拍照、定位、語音備註,回辦公室前就能交棒</h2>
          <p>適合活動場地、動線、入口、電源、停車、風險問題。完成後可複製場勘 brief 或推到工作包。</p>
        </div>
        <div class="module-hero-metrics">
          <div><strong>${this._images.length}</strong><span>已選照片</span></div>
          <div><strong>${this._gps ? "已取" : "未取"}</strong><span>定位</span></div>
          <div><strong>${this._projectId ? "已綁" : "選填"}</strong><span>工作包</span></div>
        </div>
      </section>

      <section class="module-flow-grid">
        <div><b>1. 拍照</b><span>1-5 張,JPEG / PNG / WebP / HEIC</span></div>
        <div><b>2. 加定位與備註</b><span>地址提示、GPS、完成後可補 30 秒語音</span></div>
        <div><b>3. 產出 brief</b><span>場地、入口、電源、停車、問題清單</span></div>
      </section>

      <div class="site-toolbar">
        <h2>📸 場勘紀錄</h2>
        <p class="site-desc">拍 1-5 張現場照片 · 定位自動帶入 · 智慧助理產結構化場勘摘要</p>
      </div>

      <div class="site-form">
        <div class="site-section">
          <h3>1. 拍照(已選 <b>${this._images.length}/${MAX_IMAGES}</b>)</h3>
          <div class="site-photo-grid">
            ${this._images.map((img, i) => `
              <div class="site-photo">
                <img src="${img.dataUrl}" alt="photo ${i+1}">
                <button class="site-photo-del" data-del="${i}">×</button>
              </div>
            `).join("")}
            ${this._images.length < MAX_IMAGES ? `
              <label class="site-photo-add">
                <input type="file" id="site-camera" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif" capture="environment" multiple style="display:none">
                <span>+ 加照片</span>
              </label>
            ` : ""}
          </div>
        </div>

        <div class="site-section">
          <h3>2. 定位</h3>
          ${this._gps ? `
            <div class="site-gps-ok">
              📍 緯度 ${this._gps.lat.toFixed(5)} · 經度 ${this._gps.lng.toFixed(5)}
              ${this._gps.accuracy ? `(精度 ${Math.round(this._gps.accuracy)}m)` : ""}
              <button class="btn-tiny" id="site-gps-clear">清除</button>
            </div>
          ` : `
            <button class="btn-secondary" id="site-gps-btn">📍 取得定位</button>
            <small class="site-help">瀏覽器會請求位置權限</small>
          `}
        </div>

        <div class="site-section">
          <h3>3. 地址提示(選填)</h3>
          <input type="text" id="site-address" value="${escapeHtml(this._addressHint)}"
                 placeholder="例:台北 101 4 樓 · 中山堂中正廳">
        </div>

        <div class="site-section">
          <h3>4. 綁工作包(選填 · 才能一鍵推交棒卡)</h3>
          <input type="text" id="site-project" value="${escapeHtml(this._projectId)}"
                 placeholder="工作包編號(從工作包頁複製)">
        </div>

        <div class="site-actions">
          <button class="btn-primary" id="site-submit-btn"
                  ${this._images.length === 0 ? "disabled" : ""}>
            🚀 上傳 + 智慧分析
          </button>
        </div>
      </div>

      <div class="site-history">
        <h3>歷史場勘</h3>
        <div id="site-history-list">載入中...</div>
      </div>
    `;
    this._bindEvents();
  },

  _bindEvents() {
    const root = document.getElementById("view-site-content");
    if (!root) return;

    root.querySelector("#site-camera")?.addEventListener("change", e => {
      this._addPhotos(Array.from(e.target.files));
    });
    root.querySelectorAll("[data-del]").forEach(b => {
      b.addEventListener("click", () => {
        const idx = parseInt(b.dataset.del);
        const removed = this._images.splice(idx, 1)[0];
        if (removed?.isObjectUrl && removed.dataUrl) {
          try { URL.revokeObjectURL(removed.dataUrl); } catch {}
        }
        this.render();
      });
    });
    root.querySelector("#site-gps-btn")?.addEventListener("click", () => this._getGPS());
    root.querySelector("#site-gps-clear")?.addEventListener("click", () => {
      this._gps = null;
      this.render();
    });
    root.querySelector("#site-address")?.addEventListener("input", e => {
      this._addressHint = e.target.value;
    });
    root.querySelector("#site-project")?.addEventListener("input", e => {
      this._projectId = e.target.value;
    });
    root.querySelector("#site-submit-btn")?.addEventListener("click", () => this._submit());
  },

  async _addPhotos(files) {
    const remaining = MAX_IMAGES - this._images.length;
    if (files.length > remaining) {
      toast.warn(`只能再加 ${remaining} 張`);
      files = Array.from(files).slice(0, remaining);
    }
    for (const f of files) {
      if (f.size > MAX_BYTES) {
        toast.warn(`照片過大已跳過`, { detail: `${f.name}(${(f.size / 1024 / 1024).toFixed(1)}MB > 5MB)` });
        continue;
      }
      // R24#6 · 用 objectURL 不是 dataURL · 省 33% memory(不 base64 膨脹)
      const dataUrl = URL.createObjectURL(f);
      this._images.push({ file: f, dataUrl, isObjectUrl: true });
    }
    this.render();
  },

  _revokeObjectUrls() {
    // 刪 / 清空時 revoke · 不洩漏 memory
    this._images.forEach(img => {
      if (img.isObjectUrl && img.dataUrl) {
        try { URL.revokeObjectURL(img.dataUrl); } catch {}
      }
    });
  },

  _getGPS() {
    if (!navigator.geolocation) {
      toast.error("瀏覽器不支援定位", { detail: "請改用 iPhone Safari 或 Chrome" });
      return;
    }
    toast.info("取得定位中...");
    navigator.geolocation.getCurrentPosition(
      pos => {
        this._gps = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        };
        toast.success("定位已取得");
        this.render();
      },
      err => {
        const hint = err.code === 1 ? "已被拒絕 · 到「設定 → 隱私 → 定位」開啟" : err.message;
        toast.error("定位取得失敗", {
          detail: hint,
          action: { label: "教學", onClick: () => location.hash = "#help" },
        });
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  },

  async _submit() {
    if (this._images.length === 0) {
      toast.warn("請至少拍 1 張照片");
      return;
    }
    const fd = new FormData();
    this._images.forEach(img => fd.append("images", img.file));
    if (this._gps) {
      fd.set("gps_lat", this._gps.lat);
      fd.set("gps_lng", this._gps.lng);
      if (this._gps.accuracy) fd.set("gps_accuracy", this._gps.accuracy);
    }
    if (this._addressHint) fd.set("address_hint", this._addressHint);
    if (this._projectId) fd.set("project_id", this._projectId);

    // UX(v1.3 P1#14)· 鎖 submit + 顯示 banner · 防 double-click
    const submitBtn = document.getElementById("site-submit-btn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = "⏳ 上傳中...";
    }

    try {
      const totalMB = (this._images.reduce((s, i) => s + i.file.size, 0) / 1024 / 1024).toFixed(1);
      toast.info(`上傳 ${this._images.length} 張(${totalMB}MB)...`);
      const r = await authFetch(`${BASE}/site-survey`, { method: "POST", body: fd });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("上傳場勘照片", err, () => this._submit());
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = "🚀 上傳 + 智慧分析";
        }
        return;
      }
      const body = await r.json();
      const submittedImageCount = this._images.length;
      this._currentSurveyId = body.survey_id;
      toast.success(`智慧分析中(約 ${this._images.length * 6} 秒)`);
      markTaskDone("tutorial-site-photo");
      // R24#6 · revoke objectURLs 釋放 memory
      this._revokeObjectUrls();
      this._images = [];
      this._gps = null;
      this._addressHint = "";
      this.render();
      this._startPolling();
      this._showProcessingBanner(body.survey_id, submittedImageCount);
    } catch (e) {
      networkError("上傳場勘照片", e, () => this._submit());
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = "🚀 上傳 + 智慧分析";
      }
    }
  },

  _showProcessingBanner(surveyId, imageCount) {
    // P1#14 · main view 上方顯示 banner · 跟 meeting.js 同 pattern
    const root = document.getElementById("view-site-content");
    if (!root) return;
    let banner = document.getElementById("site-processing-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "site-processing-banner";
      banner.className = "banner-processing";
      root.prepend(banner);
    }
    let elapsed = 0;
    banner.innerHTML = `<div class="loading-spinner" style="width:18px; height:18px; border:2px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:spin 0.8s linear infinite;"></div>
      <div style="flex:1">
        <div style="font-weight:600">📸 場勘智慧分析中(紀錄 ${surveyId.slice(-6)})</div>
        <div id="site-banner-timer" style="font-size:12px; color:var(--text-secondary)">已 ${elapsed}s · 視覺模型處理 ${imageCount} 張照片中</div>
      </div>`;
    if (this._bannerTimer) clearInterval(this._bannerTimer);
    this._bannerTimer = setInterval(() => {
      elapsed += 1;
      const t = document.getElementById("site-banner-timer");
      if (t) t.textContent = `已 ${elapsed}s · 視覺模型處理中`;
    }, 1000);
  },

  _hideProcessingBanner() {
    const banner = document.getElementById("site-processing-banner");
    if (banner) banner.remove();
    if (this._bannerTimer) {
      clearInterval(this._bannerTimer);
      this._bannerTimer = null;
    }
  },

  _startPolling() {
    if (this._pollTimer) clearInterval(this._pollTimer);
    let attempts = 0;
    // v1.3 batch6 · stale closure 修 · 把 ID 局部存
    const pollId = this._currentSurveyId;
    this._pollTimer = setInterval(async () => {
      attempts++;
      if (attempts > 30) {
        clearInterval(this._pollTimer);
        this._hideProcessingBanner();
        toast.error("智慧分析超時(90 秒)", {
          detail: "可能模型服務金鑰失效 · 或模型服務暫慢",
          action: { label: "看歷史", onClick: () => this._loadHistory() },
        });
        return;
      }
      try {
        const r = await authFetch(`${BASE}/site-survey/${pollId}`);
        if (!r.ok) return;
        const body = await r.json();
        if (body.status === "done") {
          clearInterval(this._pollTimer);
          this._hideProcessingBanner();
          this._showResult(body);
          this._loadHistory();
        } else if (body.status === "failed") {
          clearInterval(this._pollTimer);
          this._hideProcessingBanner();
          toast.error("場勘處理失敗", {
            detail: body.error || "未知錯誤",
            action: { label: "故障排除", onClick: () => location.hash = "#help" },
          });
        }
      } catch {}
    }, 3000);
  },

  _showResult(body) {
    const s = body.structured || {};
    const root = document.getElementById("modal-root") || document.body;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.innerHTML = `
      <div class="modal2-box" style="max-width:600px; max-height:80vh; overflow-y:auto">
        <div class="modal2-header">✅ 場勘智慧分析完成</div>

        ${s.venue ? `
          <h3>🏛 場地</h3>
          <p><b>${escapeHtml(s.venue.type || "?")}</b> · ${escapeHtml(s.venue.size_estimate || "?")}</p>
        ` : ""}

        ${s.entrances?.length ? `
          <h3>🚪 入口</h3>
          <ul>${s.entrances.map(e => `<li>${escapeHtml(e)}</li>`).join("")}</ul>
        ` : ""}

        ${s.toilets_count !== undefined && s.toilets_count !== null ? `
          <p><b>🚻 洗手間:</b> ${s.toilets_count} 處</p>
        ` : ""}

        ${s.parking ? `<p><b>🚗 停車:</b> ${escapeHtml(s.parking)}</p>` : ""}
        ${s.power_outlets ? `<p><b>🔌 電源:</b> ${escapeHtml(s.power_outlets)}</p>` : ""}

        ${s.issues?.length ? `
          <h3>⚠️ 問題</h3>
          <ul>${s.issues.map(i => `<li style="color:#ef4444">${escapeHtml(i)}</li>`).join("")}</ul>
        ` : ""}

        <details style="margin-top:16px">
          <summary>各照片智慧描述(${(body.media || []).length} 張)</summary>
          ${(body.media || []).map((p, i) => `
            <div style="margin-top:8px; padding:8px; background:var(--surface-2); border-radius:6px">
              <b>照片 ${i + 1}:</b> ${escapeHtml(p.caption_ai || "")}
              ${p.error ? `<small style="color:#ef4444"> · ${escapeHtml(p.error)}</small>` : ""}
            </div>
          `).join("")}
        </details>

        <details style="margin-top:16px" open>
          <summary>🎙 語音備註(${(body.audio_notes || []).length})</summary>
          <div id="site-audio-list">
            ${(body.audio_notes || []).map((a, i) => `
              <div style="margin-top:8px; padding:8px; background:var(--surface-2); border-radius:6px">
                <b>${i + 1}.</b>
                ${a.status === "done"
                  ? `<span>${escapeHtml(a.transcript || "")}</span>`
                  : a.status === "failed"
                  ? `<span style="color:#ef4444">失敗 · ${escapeHtml(a.error || "")}</span>`
                  : `<span style="color:var(--text-secondary)">⏳ 處理中…</span>`}
                ${a.duration_sec ? `<small style="color:var(--text-secondary)"> · ${a.duration_sec.toFixed?.(1) || a.duration_sec}s</small>` : ""}
              </div>
            `).join("")}
          </div>
          <div style="margin-top:12px">
            <button type="button" id="site-audio-rec" class="btn-secondary">🎙 錄 30 秒</button>
            <span id="site-audio-status" style="margin-left:12px; color:var(--text-secondary); font-size:13px"></span>
          </div>
        </details>

        <div class="modal2-actions">
          <button type="button" data-close>關閉</button>
          <button type="button" data-copy>複製場勘 brief</button>
          ${body.project_id ? `<button type="button" class="primary" data-push>推到交棒卡</button>` : ""}
        </div>
      </div>
    `;
    root.appendChild(m);
    m.querySelector("[data-close]").addEventListener("click", () => m.remove());
    m.querySelector("[data-copy]").addEventListener("click", async () => {
      await copyText(siteBriefText(body));
      toast.success("場勘 brief 已複製");
      markTaskDone("tutorial-site-brief-copy");
    });
    // B4 · 錄音按鈕
    m.querySelector("#site-audio-rec")?.addEventListener("click", async () => {
      await this._recordAudio(m);
    });
    m.querySelector("[data-push]")?.addEventListener("click", async () => {
      try {
        const r = await authFetch(`${BASE}/site-survey/${this._currentSurveyId}/push-to-handoff`, { method: "POST" });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          operationError("推到交棒卡", err);
          return;
        }
        const body = await r.json();
        toast.success(`已推 · ${body.issues_count} 個問題進交棒卡`);
        markTaskDone("tutorial-site-push-handoff");
        m.remove();
      } catch (e) {
        networkError("推到交棒卡", e);
      }
    });
  },

  async _loadHistory() {
    const list = document.getElementById("site-history-list");
    if (!list) return;
    try {
      const r = await authFetch(`${BASE}/site-survey?limit=10`);
      const body = await r.json();
      const items = body.items || [];
      if (!items.length) {
        list.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📸</div>
            <div class="empty-state-title">尚無場勘紀錄</div>
            <div class="empty-state-hint">拍 1-5 張現場照片 + 定位 · 智慧助理自動結構化</div>
          </div>`;
        return;
      }
      list.innerHTML = items.map(s => `
        <div class="site-history-item" data-site-survey-id="${escapeHtml(s.survey_id)}">
          <span>📸 ${s.image_count} 張</span>
          <span>${escapeHtml(s.venue_type || "未分析")}</span>
          <span>${s.issues_count > 0 ? `⚠️ ${s.issues_count} 問題` : "✅ 無問題"}</span>
          <span class="site-history-time">${this._formatTime(s.created_at)}</span>
          <span class="site-history-status status-${s.status}">${this._statusLabel(s.status)}</span>
        </div>
      `).join("");
      list.querySelectorAll("[data-site-survey-id]").forEach(el => {
        el.addEventListener("click", () => this._openSurvey(el.getAttribute("data-site-survey-id")));
      });
    } catch (e) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">😓</div>
          <div class="empty-state-title">讀取歷史失敗</div>
          <div class="empty-state-hint">${escapeHtml(e?.message || "網路或伺服器錯")}</div>
          <button class="btn-ghost" data-action="siteSurvey.loadHistory" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  _formatTime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  },

  _statusLabel(status) {
    return {
      pending: "處理中",
      done: "完成",
      failed: "失敗",
    }[status] || "未知";
  },

  // B4(v1.3)· 30 秒錄音 + 上傳 + Whisper STT
  async _recordAudio(modal) {
    const status = modal.querySelector("#site-audio-status");
    const btn = modal.querySelector("#site-audio-rec");
    if (!navigator.mediaDevices?.getUserMedia) {
      status.textContent = "❌ 瀏覽器不支援錄音(iOS Safari 16+ / Chrome / Firefox)";
      return;
    }
    if (!window.MediaRecorder) {
      status.textContent = "❌ 瀏覽器錄音功能不支援";
      return;
    }
    btn.disabled = true;
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      status.textContent = `❌ 麥克風權限被拒:${e.message}`;
      btn.disabled = false;
      return;
    }
    // iPhone Safari 16+ 支援 audio/mp4 · 其他預設 audio/webm
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "";
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
    const chunks = [];
    rec.ondataavailable = (ev) => { if (ev.data?.size) chunks.push(ev.data); };

    const startTime = Date.now();
    rec.start();
    btn.textContent = "⏹ 停 (錄 30s)";
    btn.disabled = false;

    let countdown = 30;
    status.textContent = `🎙 錄音中… ${countdown}s`;
    const tick = setInterval(() => {
      countdown -= 1;
      status.textContent = `🎙 錄音中… ${countdown}s`;
      if (countdown <= 0) {
        rec.state === "recording" && rec.stop();
      }
    }, 1000);

    const stopAndUpload = () => new Promise((resolve) => {
      rec.onstop = async () => {
        clearInterval(tick);
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        const durationSec = (Date.now() - startTime) / 1000;
        status.textContent = "📤 上傳 · 語音轉文字中…";
        try {
          const fd = new FormData();
          // .webm / .mp4 副檔名以便 Whisper 識別
          const ext = (rec.mimeType || "audio/webm").includes("mp4") ? "mp4" : "webm";
          fd.append("audio", blob, `audio.${ext}`);
          fd.append("duration_sec", String(durationSec));
          const r = await authFetch(
            `${BASE}/site-survey/${this._currentSurveyId}/audio`,
            { method: "POST", body: fd },
          );
          if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            status.textContent = `❌ 上傳失敗:${err.detail || r.status}`;
            resolve(false);
            return;
          }
          status.textContent = "✅ 上傳成功 · 語音轉文字背景處理中 · 重新開啟可看結果";
          resolve(true);
        } catch (e) {
          status.textContent = `❌ 網路錯:${String(e)}`;
          resolve(false);
        }
      };
    });

    btn.onclick = () => {
      if (rec.state === "recording") {
        rec.stop();
      }
    };
    await stopAndUpload();
    btn.textContent = "🎙 錄下一段";
    btn.disabled = false;
    btn.onclick = () => this._recordAudio(modal);  // restore handler
  },

  async _openSurvey(surveyId) {
    try {
      const r = await authFetch(`${BASE}/site-survey/${surveyId}`);
      if (!r.ok) {
        operationError("讀取場勘", await r.json().catch(() => ({})));
        return;
      }
      const body = await r.json();
      this._currentSurveyId = surveyId;
      this._showResult(body);
    } catch (e) {
      networkError("讀取場勘", e, () => this._openSurvey(surveyId));
    }
  },
};

function siteBriefText(body = {}) {
  const s = body.structured || {};
  const venue = s.venue || {};
  const lines = [
    "場勘 brief",
    `場地:${venue.type || "未判斷"} · ${venue.size_estimate || "未估算"}`,
    `照片:${body.image_count || (body.media || []).length || 0} 張`,
  ];
  const loc = body.location || {};
  if (loc.address_hint) lines.push(`地址提示:${loc.address_hint}`);
  if (Array.isArray(s.entrances) && s.entrances.length) {
    lines.push("", "入口");
    s.entrances.forEach(x => lines.push(`- ${x}`));
  }
  if (s.power_outlets) lines.push(`電源:${s.power_outlets}`);
  if (s.parking) lines.push(`停車:${s.parking}`);
  if (s.toilets_count !== undefined && s.toilets_count !== null) lines.push(`洗手間:${s.toilets_count} 處`);
  if (Array.isArray(s.issues) && s.issues.length) {
    lines.push("", "風險 / 待確認");
    s.issues.forEach(x => lines.push(`- ${x}`));
  }
  const audio = body.audio_notes || [];
  const transcripts = audio.filter(a => a.status === "done" && a.transcript);
  if (transcripts.length) {
    lines.push("", "現場語音備註");
    transcripts.forEach((a, idx) => lines.push(`- ${idx + 1}. ${a.transcript}`));
  }
  return lines.join("\n").trim();
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
}
