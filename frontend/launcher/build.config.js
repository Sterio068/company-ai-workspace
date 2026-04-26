/**
 * v1.9 perf · esbuild build config(launcher prod bundle)
 *
 * 目的:
 *   29 個 .js module 慢網下並行 RTT 堆積 · launcher 進入 1.2s
 *   bundle + minify + content-hash + 1-year immutable cache → 進入 < 0.5s
 *
 * 用法:
 *   cd frontend/launcher
 *   npm install   # 第一次裝 esbuild
 *   npm run build # 產 dist/* + dist/manifest.json + 注入 index.html
 *
 * v1.9 cutover · build 後自動把 index.html 的 <script src> 改指 dist/ hash 檔
 * nginx 已加 /static/dist/ immutable cache(default.conf v1.9)
 *
 * watch mode(dev):
 *   npm run build:watch
 */
import esbuild from "esbuild";
import { existsSync, mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const isWatch = process.argv.includes("--watch");

const buildOptions = {
  entryPoints: [
    "app.js",         // 主 entry · ES module · 自動 follow imports 含 29 modules
    "onboarding.js",  // 另一 entry · 4 步引導
  ],
  bundle: true,
  outdir: "dist",
  format: "esm",
  target: ["es2020", "safari16", "chrome120"],  // 對應 launcher 用戶 browser
  minify: !isWatch,         // dev 不 minify · 易 debug
  sourcemap: true,
  splitting: true,          // 共用 chunk 自動拆 · vendor 與 app code 分
  treeShaking: true,
  metafile: true,
  // 自動 hash filename · 強制 browser cache 失效
  entryNames: "[name].[hash]",
  chunkNames: "chunks/[name].[hash]",
  assetNames: "assets/[name].[hash]",
  logLevel: "info",
};

async function build() {
  if (!existsSync("dist")) mkdirSync("dist", { recursive: true });

  if (isWatch) {
    const ctx = await esbuild.context(buildOptions);
    await ctx.watch();
    console.log("⚙ watch mode · 改檔自動重 build");
    return;
  }

  const result = await esbuild.build(buildOptions);

  // 產 manifest.json · 給 nginx / index.html 對應 hash filename
  // 例:{"app.js": "app.X3K2.js", "onboarding.js": "onboarding.AB12.js"}
  const manifest = {};
  for (const [outputPath, info] of Object.entries(result.metafile.outputs)) {
    if (info.entryPoint) {
      const entryName = info.entryPoint.replace(/\.js$/, "");
      manifest[`${entryName}.js`] = outputPath.replace(/^dist\//, "");
    }
  }
  writeFileSync("dist/manifest.json", JSON.stringify(manifest, null, 2));
  console.log("✅ bundle done · dist/manifest.json:");
  console.log(JSON.stringify(manifest, null, 2));

  // v1.9 · 自動把 index.html 的 <script src="/static/app.js?v=N">
  //              改成 <script src="/static/dist/app.<hash>.js">
  // 找 BUNDLE_INJECT 標記區塊一次替換 · 安全可重跑
  patchIndexHtml(manifest);
}

function patchIndexHtml(manifest) {
  const htmlPath = join(__dirname, "index.html");
  if (!existsSync(htmlPath)) {
    console.warn("⚠ index.html 不在 · skip patch");
    return;
  }
  let html = readFileSync(htmlPath, "utf8");

  // 標記區塊(若不存在 · 第一次 build 自動加)
  const startTag = "<!-- BUILD_INJECT_BUNDLE_START -->";
  const endTag = "<!-- BUILD_INJECT_BUNDLE_END -->";

  const appHash = manifest["app.js"];
  const onbHash = manifest["onboarding.js"];
  if (!appHash || !onbHash) {
    console.error("❌ manifest 缺 app.js / onboarding.js · skip patch");
    return;
  }

  const newBlock = `${startTag}
<script type="module" src="/static/dist/${appHash}"></script>
<script type="module" src="/static/dist/${onbHash}"></script>
${endTag}`;

  if (html.includes(startTag) && html.includes(endTag)) {
    // 替換已有區塊
    const re = new RegExp(`${startTag}[\\s\\S]*?${endTag}`, "g");
    html = html.replace(re, newBlock);
    console.log("📝 index.html · 替換 BUILD_INJECT_BUNDLE 區塊");
  } else {
    // 找原始 <script src="/static/app.js"...> + onboarding 並包入標記
    const oldRe = /<script[^>]*src="\/static\/app\.js[^"]*"[^>]*><\/script>\s*<script[^>]*src="\/static\/onboarding\.js[^"]*"[^>]*><\/script>/;
    if (oldRe.test(html)) {
      html = html.replace(oldRe, newBlock);
      console.log("📝 index.html · 首次注入 · 替換原始 script tag");
    } else {
      console.warn("⚠ index.html 找不到原始 script tag · skip(請手動加標記)");
      return;
    }
  }
  writeFileSync(htmlPath, html);
  console.log(`✅ index.html · 指向 dist/${appHash} + dist/${onbHash}`);
}

build().catch((err) => {
  console.error("❌ build fail:", err);
  process.exit(1);
});
