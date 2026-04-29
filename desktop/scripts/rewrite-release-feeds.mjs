import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, "..", "dist");
const proxyUrl = (process.env.VOTER_SERVICE_UPDATE_PROXY_URL || "").trim().replace(/\/+$/, "");

if (!proxyUrl) {
  console.log("skip feed rewrite: VOTER_SERVICE_UPDATE_PROXY_URL is not set");
  process.exit(0);
}

function proxyAssetUrl(assetName) {
  return `${proxyUrl}/api/updates/assets/${encodeURIComponent(assetName)}`;
}

function rewriteFeed(fileName) {
  const filePath = path.join(distDir, fileName);
  if (!fs.existsSync(filePath)) return;
  const input = fs.readFileSync(filePath, "utf8");
  const output = input.split(/\r?\n/).map((line) => {
    const match = line.match(/^(\s*(?:-\s*)?)(url|path):\s*(.+?)\s*$/);
    if (!match) return line;
    const [, indent, key, raw] = match;
    const value = raw.trim().replace(/^['"]|['"]$/g, "");
    const assetName = decodeURIComponent(
      path.basename(new URL(value, "https://placeholder.invalid/").pathname),
    );
    if (!assetName || /\.(ya?ml)$/i.test(assetName)) return line;
    return `${indent}${key}: ${proxyAssetUrl(assetName)}`;
  }).join("\n");
  fs.writeFileSync(filePath, output);
  console.log(`${fileName} rewritten to proxy asset URLs`);
}

rewriteFeed("latest.yml");
rewriteFeed("latest-mac.yml");
