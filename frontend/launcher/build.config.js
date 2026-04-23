/**
 * v1.3 A3 · esbuild build config(launcher prod bundle)
 *
 * 目的:
 *   29 個 .js module 慢網下並行 RTT 堆積 · launcher 進入 1.2s
 *   bundle 後 1 個檔 + minify + sourcemap · 進入 < 0.5s 估
 *
 * 用法:
 *   cd frontend/launcher
 *   npm install   # 第一次裝 esbuild
 *   npm run build # 產 dist/app.[hash].js + dist/manifest.json
 *
 * 切換 nginx 改 mount /static/ → dist/(此 PR 不做 · 留 v1.4 cutover)
 *   見 docs/04-OPERATIONS.md §A3 cutover
 *
 * watch mode(dev):
 *   npm run build:watch
 */
import esbuild from "esbuild";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
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
  console.log("✅ build done · dist/manifest.json:");
  console.log(JSON.stringify(manifest, null, 2));
}

build().catch((err) => {
  console.error("❌ build fail:", err);
  process.exit(1);
});
