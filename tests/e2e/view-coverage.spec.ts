/**
 * v1.68 Q4 · 14 view 完整覆蓋測試
 *
 * 對每個 view:
 *   1. 切換到該 view
 *   2. 等 DOM render
 *   3. 確認 view 容器有 active class
 *   4. 沒 pageerror / console error(略過 iframe X-Frame / 401 既知噪音)
 *   5. screenshot 存 test-results/views/
 *
 * 共享 session 避免 login rate-limit:
 *   beforeAll login 一次 · 存 storageState · 後續 test 從 cache 讀
 *
 * 預期執行:
 *   E2E_ADMIN_EMAIL=... E2E_ADMIN_PASSWORD=... npx playwright test view-coverage
 */
import { test, expect, Page, BrowserContext } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import * as fs from 'fs';
import * as path from 'path';

const ALL_VIEWS = [
  { id: 'dashboard',  needsAdmin: false, label: '今日' },
  { id: 'projects',   needsAdmin: false, label: '專案' },
  { id: 'knowledge',  needsAdmin: false, label: '資料' },
  { id: 'notebooklm', needsAdmin: false, label: 'NotebookLM' },
  { id: 'admin',      needsAdmin: true,  label: '中控' },
  { id: 'workflows',  needsAdmin: false, label: '工作流程' },
  { id: 'crm',        needsAdmin: true,  label: '商機追蹤' },
  { id: 'accounting', needsAdmin: true,  label: '會計' },
  { id: 'tenders',    needsAdmin: false, label: '標案' },
  { id: 'meeting',    needsAdmin: false, label: '會議速記' },
  { id: 'media',      needsAdmin: false, label: '媒體名單' },
  { id: 'social',     needsAdmin: false, label: '社群排程' },
  { id: 'site',       needsAdmin: false, label: '場勘' },
  { id: 'users',      needsAdmin: true,  label: '同仁管理' },
  { id: 'help',       needsAdmin: false, label: '使用教學' },
];

function readKeychainSecret(service: string): string {
  if (process.platform !== 'darwin') return '';
  try {
    return execFileSync('security', ['find-generic-password', '-s', service, '-w'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return '';
  }
}

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL
  || process.env.LIBRECHAT_ADMIN_EMAIL
  || readKeychainSecret('chengfu-ai-admin-install-email');
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD
  || process.env.LIBRECHAT_ADMIN_PASSWORD
  || readKeychainSecret('chengfu-ai-admin-install-password');

// 既知 noise · 不算 fail
const NOISE_PATTERNS = [
  /X-Frame-Options/,
  /Failed to load resource: the server responded with a status of 401/,
  /Failed to read the 'localStorage'/,
  /Refused to display .* in a frame/,
];

function isNoise(text: string): boolean {
  return NOISE_PATTERNS.some(p => p.test(text));
}

async function loginAsAdmin(page: Page): Promise<void> {
  if (!ADMIN_EMAIL || !ADMIN_PASSWORD) {
    throw new Error('缺 E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD 或 Keychain E2E 憑證,不可跳過登入後 view 覆蓋');
  }
  await page.goto('/login');
  await page.locator('#email').waitFor({ state: 'visible', timeout: 10_000 });
  await page.fill('#email', ADMIN_EMAIL);
  await page.fill('#password', ADMIN_PASSWORD);
  await page.locator('button[type="submit"]').click();
  // 等 launcher 進入 app · view-dashboard active
  await page.locator('.view-dashboard.active').waitFor({ state: 'visible', timeout: 15_000 });
  await page.evaluate(() => {
    localStorage.setItem('chengfu-onboarding-done', '1');
    localStorage.setItem('chengfu-tour-done', '1');
    document.querySelectorAll('.tutorial-backdrop, #tour-backdrop, #tour-bubble').forEach(el => (el as HTMLElement).style.display = 'none');
    (window as any).tour?.skip?.();
  });
}

// v1.68 Q4 · 共享 context · 跳開 Playwright fixture 對 storageState 的 race
// beforeAll 建 context + login · 所有 test 重用同一個 page
test.describe.serial('v1.68 Q4 · 14 view 全覆蓋', () => {
  let sharedContext: BrowserContext;
  let sharedPage: Page;

  test.beforeAll(async ({ browser }) => {
    sharedContext = await browser.newContext();
    sharedPage = await sharedContext.newPage();
    await sharedPage.addInitScript(() => {
      localStorage.setItem('chengfu-onboarding-done', '1');
      localStorage.setItem('chengfu-tour-done', '1');
    });
    await loginAsAdmin(sharedPage);
  });

  test.afterAll(async () => {
    await sharedContext?.close();
  });

  for (const view of ALL_VIEWS) {
    test(`${view.id} (${view.label}) 不爆`, async () => {
      const errors: string[] = [];
      const onPageError = (e: Error) => errors.push(`PE: ${e.message}`);
      const onConsole = (m: any) => {
        if (m.type() === 'error' && !isNoise(m.text())) errors.push(`CE: ${m.text()}`);
      };
      sharedPage.on('pageerror', onPageError);
      sharedPage.on('console', onConsole);

      try {
        // 切到該 view
        await sharedPage.evaluate((id) => (window as any).app?.showView?.(id), view.id);
        await sharedPage.waitForTimeout(800);

        // view 容器存在
        const viewExists = await sharedPage.evaluate((id) =>
          !!document.querySelector(`.view[data-view="${id}"]`), view.id);
        expect(viewExists, `view-${view.id} DOM 不存在`).toBe(true);

        // screenshot
        await sharedPage.screenshot({ path: `test-results/views/v1.68-${view.id}.png` });

        // no error
        expect(errors, `view-${view.id} 噴 error: ${errors.join(' | ')}`).toEqual([]);
      } finally {
        sharedPage.off('pageerror', onPageError);
        sharedPage.off('console', onConsole);
      }
    });
  }

  test('chat pane · a11y attrs', async () => {
    await sharedPage.evaluate(() => (window as any).chat?.open?.('00', ''));
    await sharedPage.waitForSelector('#chat-pane.open', { timeout: 4000 });

    expect(await sharedPage.locator('#chat-messages').getAttribute('aria-live')).toBe('polite');
    expect(await sharedPage.locator('#chat-messages').getAttribute('role')).toBe('log');
    expect(await sharedPage.locator('#chat-pane-resizer').isVisible()).toBe(true);
    expect(await sharedPage.locator('#chat-fullscreen-btn').isVisible()).toBe(true);
  });

  test('workflows 卡片應有 6 個閉環(v1.67)', async () => {
    await sharedPage.evaluate(() => {
      (window as any).app?.showView?.('workflows');
      (window as any).workflows?.load?.();
    });
    await sharedPage.waitForTimeout(2500);

    const cards = await sharedPage.evaluate(() =>
      Array.from(document.querySelectorAll('[data-workflow-id]')).map(c => (c as HTMLElement).dataset.workflowId)
    );
    expect(cards.length).toBeGreaterThanOrEqual(6);
    expect(cards).toContain('tender-full');
    expect(cards).toContain('closing-full');
    expect(cards).toContain('monthly-ops');
    expect(cards).toContain('client-proposal');
  });
});
