const input = document.getElementById("base-url");
const save = document.getElementById("save");

// 載入既有設定
chrome.storage.sync.get("chengfu_base_url").then(({ chengfu_base_url }) => {
  input.value = chengfu_base_url || "http://localhost";
});

save.addEventListener("click", async () => {
  const url = input.value.trim().replace(/\/$/, "");
  if (!url) return;
  await chrome.storage.sync.set({ chengfu_base_url: url });
  save.textContent = "✅ 已儲存";
  setTimeout(() => save.textContent = "儲存", 1500);
});
