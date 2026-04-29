const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { shell } = require("electron");
const { autoUpdater } = require("electron-updater");
const { resolveUpdateProxyConfig } = require("./update-config.cjs");

function authHeaders(config) {
  return { Authorization: `Bearer ${config.updateProxyToken}` };
}

function assertProxyConfig(config) {
  if (!config.updateProxyUrl || !config.updateProxyToken) {
    throw new Error("Update proxy is not configured.");
  }
}

function updaterPlatform() {
  return process.platform === "darwin" ? "darwin" : "win32";
}

function updaterArch() {
  return process.arch === "arm64" ? "arm64" : "x64";
}

function latestMetadataUrl(config, app, forceRefresh) {
  const url = new URL(`${config.updateProxyUrl}/api/updates/latest`);
  url.searchParams.set("current", app.getVersion());
  url.searchParams.set("platform", updaterPlatform());
  url.searchParams.set("arch", updaterArch());
  if (forceRefresh) {
    url.searchParams.set("refresh", "true");
    url.searchParams.set("_", String(Date.now()));
  }
  return url.toString();
}

async function proxyJson(config, url, forceRefresh = false) {
  const res = await fetch(url, {
    headers: {
      ...authHeaders(config),
      ...(forceRefresh ? { "Cache-Control": "no-cache", Pragma: "no-cache" } : {}),
    },
  });
  if (!res.ok) throw new Error(`Update proxy HTTP ${res.status}`);
  return res.json();
}

async function downloadAsset(config, asset, destPath) {
  const res = await fetch(asset.url, {
    headers: {
      ...authHeaders(config),
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    },
  });
  if (!res.ok) throw new Error(`Update asset HTTP ${res.status}`);
  const buffer = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(destPath, buffer);
  return destPath;
}

async function checkMacUnsignedUpdate(config, app, forceRefresh) {
  const metadata = await proxyJson(config, latestMetadataUrl(config, app, forceRefresh), forceRefresh);
  if (!metadata.has_update) {
    return { hasUpdate: false, latest: metadata.latest, current: metadata.current };
  }
  if (!metadata.platform_asset?.url || !metadata.platform_asset?.name) {
    throw new Error("Update proxy did not return a macOS DMG asset.");
  }
  const dmgPath = path.join(os.tmpdir(), metadata.platform_asset.name);
  await downloadAsset(config, metadata.platform_asset, dmgPath);
  await shell.openPath(dmgPath);
  return {
    hasUpdate: true,
    latest: metadata.latest,
    current: metadata.current,
    openedDmg: true,
    message: "DMG 已開啟。未簽章 macOS 包需要使用者手動拖到 Applications 覆蓋安裝。",
  };
}

async function checkWindowsUpdate(config, app, forceRefresh) {
  const metadata = await proxyJson(config, latestMetadataUrl(config, app, forceRefresh), forceRefresh);
  if (!metadata.has_update) {
    return { hasUpdate: false, latest: metadata.latest, current: metadata.current };
  }

  autoUpdater.autoDownload = false;
  autoUpdater.requestHeaders = authHeaders(config);
  autoUpdater.setFeedURL({
    provider: "generic",
    url: `${config.updateProxyUrl}/api/updates/generic/win`,
    requestHeaders: authHeaders(config),
  });
  const result = await autoUpdater.checkForUpdates();
  return {
    hasUpdate: true,
    latest: metadata.latest,
    current: metadata.current,
    updateInfo: result?.updateInfo || null,
  };
}

async function checkForUpdates(app, { forceRefresh = false } = {}) {
  const config = resolveUpdateProxyConfig(app);
  assertProxyConfig(config);
  if (process.platform === "darwin") {
    return checkMacUnsignedUpdate(config, app, forceRefresh);
  }
  if (process.platform === "win32") {
    return checkWindowsUpdate(config, app, forceRefresh);
  }
  return { hasUpdate: false, unsupported: true, platform: process.platform };
}

function registerUpdateIpc({ app, ipcMain }) {
  ipcMain.handle("updates:check-now", async () => {
    // Manual checks always force refresh to avoid stale metadata saying "already latest".
    return checkForUpdates(app, { forceRefresh: true });
  });
}

module.exports = {
  checkForUpdates,
  registerUpdateIpc,
};
