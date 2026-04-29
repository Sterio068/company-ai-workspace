import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const outPath = path.join(root, "build", "update-proxy.json");
const checkOnly = process.argv.includes("--check");

function readEnv(name) {
  return (process.env[name] || "").trim();
}

function buildConfig() {
  return {
    schema: 1,
    installerManaged: true,
    updateProxyUrl: readEnv("VOTER_SERVICE_UPDATE_PROXY_URL").replace(/\/+$/, ""),
    updateProxyToken: readEnv("VOTER_SERVICE_UPDATE_PROXY_TOKEN"),
    generatedAt: new Date().toISOString(),
    source: "ci-extraResources",
  };
}

const config = buildConfig();

if (checkOnly) {
  if (config.updateProxyUrl && !/^https?:\/\//.test(config.updateProxyUrl)) {
    throw new Error("VOTER_SERVICE_UPDATE_PROXY_URL must be http(s) when set.");
  }
  process.exit(0);
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(config, null, 2));
console.log("update-proxy.json generated (token redacted)");
