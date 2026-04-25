(() => {
  const root = document.documentElement;
  const workspace = document.querySelector(".workspace");
  const form = document.getElementById("intake-form");
  const input = document.getElementById("mission-input");
  const fileInput = document.getElementById("mission-files");
  const ribbon = document.getElementById("file-ribbon");
  const artifactBody = document.getElementById("artifact-body");
  const artifactWindow = document.getElementById("artifact-window");
  const artifactTitle = document.getElementById("artifact-title");
  const mapTitle = document.getElementById("map-title");
  const mapDescription = document.getElementById("map-description");
  const statePill = document.getElementById("system-state");
  const sourceList = document.getElementById("source-list");
  const toast = document.getElementById("toast");
  const files = [];
  let toastTimer;

  const artifactViews = {
    brief: `
      <p class="panel-eyebrow">摘要</p>
      <h3>建議先做「有條件投標」</h3>
      <p>理由：主題契合、履約案例可補，但交通維持與保險文件是送件前風險。今天先補三份材料即可往前推。</p>
      <ol>
        <li>補過往文化活動履約實績。</li>
        <li>建立交通與人流風險表。</li>
        <li>把預算表轉成送審格式。</li>
      </ol>
    `,
    tasks: `
      <p class="panel-eyebrow">任務清單</p>
      <h3>今天 17:00 前完成三件事</h3>
      <ol>
        <li>企劃：把招標資格、評選權重與送件格式放進工作包。</li>
        <li>營運：確認保險、交通維持、臨時電與人力配置。</li>
        <li>設計：補一張主視覺方向與過往案例對照。</li>
      </ol>
    `,
    delivery: `
      <p class="panel-eyebrow">交付文件</p>
      <h3>可先輸出提案骨架</h3>
      <p>目前可以產出提案目錄、送件檢查表、風險矩陣、簡報章節與預算表欄位。每份文件都會保留引用來源。</p>
      <ol>
        <li>提案 PDF 大綱</li>
        <li>簡報 12 頁架構</li>
        <li>送件檢查表與缺件清單</li>
      </ol>
    `,
    handoff: `
      <p class="panel-eyebrow">交棒資訊</p>
      <h3>可交給企劃與營運接續</h3>
      <p>工作包會保存原始附件、摘要、決策理由、風險、待補資料與下一步負責人。</p>
      <ul>
        <li>企劃：補履約案例與提案章節。</li>
        <li>營運：確認交通維持、保險與現場人力。</li>
        <li>設計：補主視覺方向與素材清單。</li>
      </ul>
    `,
  };

  const modeCopy = {
    mission: {
      label: "任務處理",
      title: "自動整理、分派與產出",
      description: "系統會讀取需求與附件，建立摘要、分工、資料來源與交付草稿。使用者只需要確認結果。",
    },
    canvas: {
      label: "交付預覽",
      title: "同一頁預覽交付品",
      description: "摘要、任務清單、送件檢查表、提案大綱與交棒資訊可以在同一個工作包中切換。",
    },
    sources: {
      label: "資料來源",
      title: "檢查引用與套用規則",
      description: "清楚列出本次任務使用的附件、知識庫、公司規則與仍需人工確認的資料。",
    },
    flows: {
      label: "流程設定",
      title: "把常做任務存成模板",
      description: "投標判斷、活動企劃、新聞稿與結案報告可儲存為流程，下次直接套用。",
    },
  };

  document.querySelectorAll(".mode-chip").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".mode-chip").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      workspace.dataset.mode = button.dataset.mode;
      const copy = modeCopy[button.dataset.mode] || modeCopy.mission;
      mapTitle.textContent = copy.title;
      mapDescription.textContent = copy.description;
      artifactWindow.classList.add("pulse");
      window.setTimeout(() => artifactWindow.classList.remove("pulse"), 680);
    });
  });

  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.dataset.prompt;
      input.focus();
      showToast("已帶入範例任務，可以直接建立草稿。");
    });
  });

  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "light" ? "" : "light";
  });

  document.getElementById("attach-trigger")?.addEventListener("click", () => fileInput.click());

  fileInput?.addEventListener("change", () => {
    addFiles([...fileInput.files]);
    fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    form?.addEventListener(eventName, (event) => {
      event.preventDefault();
      form.classList.add("dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    form?.addEventListener(eventName, (event) => {
      event.preventDefault();
      form.classList.remove("dragging");
    });
  });

  form?.addEventListener("drop", (event) => addFiles([...event.dataTransfer.files]));

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text && files.length === 0) {
      input.placeholder = "先輸入任務，或加入一份附件。";
      input.focus();
      showToast("需要任務文字或附件，才能建立草稿。");
      return;
    }

    workspace.dataset.state = "processing";
    statePill.textContent = "處理中";
    updateProcess(1);
    window.setTimeout(() => updateProcess(2), 260);
    window.setTimeout(() => updateProcess(3), 520);
    window.setTimeout(() => {
      updateProcess(4);
      statePill.textContent = "草稿完成";
      artifactTitle.textContent = "新任務 · 草稿已建立";
      artifactBody.innerHTML = generatedArtifact(text, files.map((file) => file.name));
      renderSources(files.map((file) => file.name));
      artifactWindow.classList.add("pulse");
      window.setTimeout(() => artifactWindow.classList.remove("pulse"), 680);
      input.value = "";
      files.splice(0, files.length);
      renderFiles();
      showToast("任務草稿已建立，可檢查來源或存成工作包。");
    }, 800);
  });

  document.querySelectorAll("[data-artifact]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-artifact]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      artifactBody.innerHTML = artifactViews[button.dataset.artifact] || artifactViews.brief;
    });
  });

  document.querySelectorAll("[data-output]").forEach((button) => {
    button.addEventListener("click", () => {
      showToast(`${button.dataset.output}已加入交付預覽。`);
      document.querySelector('[data-artifact="delivery"]')?.click();
    });
  });

  document.getElementById("save-package")?.addEventListener("click", () => {
    document.querySelector('[data-artifact="handoff"]')?.click();
    showToast("已建立工作包，可交給同事接續。");
  });

  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      form?.requestSubmit();
    }
  });

  function addFiles(items) {
    for (const file of items) {
      if (files.length >= 6) break;
      files.push({
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        name: file.name,
      });
    }
    renderFiles();
    if (items.length) showToast(`已加入 ${Math.min(items.length, 6)} 個附件。`);
  }

  function renderFiles() {
    ribbon.innerHTML = "";
    for (const file of files) {
      const chip = document.createElement("span");
      chip.className = "file-chip";
      chip.innerHTML = `<span>${escapeHtml(file.name)}</span><button type="button" aria-label="移除 ${escapeHtml(file.name)}">×</button>`;
      chip.querySelector("button").addEventListener("click", () => {
        const index = files.findIndex((item) => item.id === file.id);
        if (index >= 0) files.splice(index, 1);
        renderFiles();
      });
      ribbon.appendChild(chip);
    }
  }

  function renderSources(filenames) {
    const fileButtons = filenames.length
      ? filenames.map((name) => `<button type="button">${escapeHtml(name)} <span>已讀</span></button>`).join("")
      : `<button type="button">文字任務 <span>已讀</span></button>`;
    sourceList.innerHTML = `
      ${fileButtons}
      <button type="button">公司履約案例 <span>引用</span></button>
      <button type="button">承富語氣規則 <span>套用</span></button>
    `;
  }

  function updateProcess(activeIndex) {
    const steps = [...document.querySelectorAll("#process-list li")];
    steps.forEach((step, index) => {
      step.classList.toggle("done", index < activeIndex - 1);
      step.classList.toggle("active", index === activeIndex - 1);
      const label = step.querySelector("span");
      if (!label) return;
      if (index < activeIndex - 1) label.textContent = "已完成";
      if (index === activeIndex - 1) label.textContent = activeIndex === steps.length ? "可輸出" : "處理中";
      if (index > activeIndex - 1) label.textContent = index === steps.length - 1 ? "可輸出" : "下一步";
    });
  }

  function generatedArtifact(text, filenames) {
    const safeText = escapeHtml(text || "請整理附件，產出摘要、任務清單與交付草稿。");
    const fileLine = filenames.length
      ? `<p>已納入附件：${filenames.map(escapeHtml).join("、")}</p>`
      : "<p>目前未附檔，會先依文字任務建立草稿。</p>";
    return `
      <p class="panel-eyebrow">剛生成 · 可存成工作包</p>
      <h3>任務草稿已建立</h3>
      <p>${safeText}</p>
      ${fileLine}
      <ol>
        <li>系統：先判斷資料完整度、交付格式與風險。</li>
        <li>投標模組：產 Go / No-Go、缺件清單與送件檢查表。</li>
        <li>營運模組：補分工、時程、成本與風險。</li>
      </ol>
    `;
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
})();
