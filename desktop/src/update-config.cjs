const fs = require("node:fs");
const path = require("node:path");

function safeReadJson(filePath) {
  try {
    if (!filePath || !fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function normalizeConfig(raw = {}) {
  return {
    schema: Number(raw.schema || 1),
    installerManaged: raw.installerManaged !== false,
    updateProxyUrl: String(raw.updateProxyUrl || "").replace(/\/+$/, ""),
    updateProxyToken: String(raw.updateProxyToken || ""),
    generatedAt: raw.generatedAt || null,
  };
}

function bundledConfigPath(app) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "update-proxy.json");
  }
  return path.join(__dirname, "..", "build", "update-proxy.json");
}

function installedConfigPath(app) {
  return path.join(app.getPath("userData"), "update-proxy.json");
}

function writeInstalledConfig(app, config) {
  const target = installedConfigPath(app);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify(config, null, 2));
}

function resolveUpdateProxyConfig(app) {
  const bundled = normalizeConfig(safeReadJson(bundledConfigPath(app)) || {});
  const installedPath = installedConfigPath(app);
  const installedRaw = safeReadJson(installedPath);
  const installed = installedRaw ? normalizeConfig(installedRaw) : null;

  if (!installed) {
    if (bundled.updateProxyUrl && bundled.updateProxyToken) {
      writeInstalledConfig(app, bundled);
    }
    return bundled;
  }

  if (bundled.installerManaged && installed.installerManaged && (
    bundled.updateProxyUrl !== installed.updateProxyUrl ||
    bundled.updateProxyToken !== installed.updateProxyToken ||
    bundled.generatedAt !== installed.generatedAt
  )) {
    writeInstalledConfig(app, bundled);
    return bundled;
  }

  return installed;
}

module.exports = {
  bundledConfigPath,
  installedConfigPath,
  resolveUpdateProxyConfig,
};
