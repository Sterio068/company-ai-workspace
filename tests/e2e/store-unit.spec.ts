/**
 * v1.15 · store.js unit test runner via Playwright
 * =====================================================
 * 把 frontend/launcher/tests/store.test.html 的 11 個 unit test
 * 透過 Playwright 在 headless Chrome 跑 · CI 可用
 *
 * 不需 Docker / LibreChat / nginx · 只需:
 *   - python3 -m http.server(spawn 在 tests/e2e/)
 *   - 載入 store.test.html
 *   - 從 window.__store_test_summary 讀結果
 *
 * 跑:
 *   cd tests/e2e
 *   npx playwright test store-unit.spec.ts
 */
import { test, expect } from '@playwright/test';
import { spawn, ChildProcess } from 'node:child_process';
import * as path from 'node:path';
import * as fs from 'node:fs';

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const PORT = 18765;
const TEST_PAGE = `http://localhost:${PORT}/launcher/tests/store.test.html`;

let server: ChildProcess | null = null;

test.describe('v1.11 store unit tests', () => {
  test.beforeAll(async () => {
    // Spin up python http.server pointing at frontend/(launcher 在 launcher/)
    const frontendDir = path.join(REPO_ROOT, 'frontend');
    if (!fs.existsSync(path.join(frontendDir, 'launcher', 'modules', 'store.js'))) {
      throw new Error('store.js not found · v1.11 PR 應已 merge');
    }
    server = spawn('python3', ['-m', 'http.server', String(PORT), '--directory', frontendDir], {
      stdio: 'pipe',
    });
    // wait for boot
    await new Promise(r => setTimeout(r, 1500));
  });

  test.afterAll(async () => {
    if (server) {
      server.kill('SIGTERM');
      await new Promise(r => setTimeout(r, 200));
    }
  });

  test('11 store unit test 全綠', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', e => errors.push(`PAGE: ${e.message}`));

    await page.goto(TEST_PAGE, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);  // run all tests

    // 檢查有沒有 page error
    expect(errors, `unexpected pageerror:\n${errors.join('\n')}`).toEqual([]);

    // 從 window 讀 summary
    const summary = await page.evaluate(() => (window as any).__store_test_summary);
    expect(summary, 'window.__store_test_summary 缺 · store.test.html 沒跑完').toBeTruthy();
    expect(summary.fail, `${summary.fail} 個 store unit test 失敗`).toBe(0);
    expect(summary.pass, 'pass count 不足 · 應 >= 11').toBeGreaterThanOrEqual(11);
  });
});
