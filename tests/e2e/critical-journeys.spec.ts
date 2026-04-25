import { test, expect, type BrowserContext, type Page, type TestInfo } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

/**
 * 承富 AI 關鍵 user journey
 *
 * 執行前提:
 *   1. docker compose up -d
 *   2. 跑過 seed-demo-data.py(有 3 專案 + 資料)
 *   3. 需登入的測試請提供 E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD
 */

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

const adminEmail = process.env.E2E_ADMIN_EMAIL
  || process.env.LIBRECHAT_ADMIN_EMAIL
  || readKeychainSecret('chengfu-ai-admin-install-email');
const adminPassword = process.env.E2E_ADMIN_PASSWORD
  || process.env.LIBRECHAT_ADMIN_PASSWORD
  || readKeychainSecret('chengfu-ai-admin-install-password');
const hasAdminCredentials = Boolean(adminEmail && adminPassword);
const baseURL = process.env.BASE_URL || 'http://localhost';
const authStateSlug = [
  baseURL,
  adminEmail || 'missing-admin',
].join('__').replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '').toLowerCase() || 'localhost';
const authStatePath = path.join(os.tmpdir(), `chengfu-e2e-auth-${authStateSlug}.json`);

function contextOptionsForProject(testInfo: TestInfo) {
  const projectUse = testInfo.project.use as Record<string, unknown>;
  const entries = [
    ['locale', 'zh-TW'],
    ['viewport', projectUse.viewport],
    ['userAgent', projectUse.userAgent],
    ['deviceScaleFactor', projectUse.deviceScaleFactor],
    ['isMobile', projectUse.isMobile],
    ['hasTouch', projectUse.hasTouch],
    ['colorScheme', projectUse.colorScheme],
    ['timezoneId', projectUse.timezoneId],
  ].filter(([, value]) => value !== undefined);
  return Object.fromEntries(entries);
}

async function skipTour(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('chengfu-tour-done', '1');
    (window as any).tour?.skip?.();
    document.querySelector('#tour-backdrop')?.classList.remove('open');
    document.querySelector('#tour-bubble')?.classList.remove('open');
  });
}

async function loginAsAdmin(page: Page) {
  await page.goto('/login');
  await expect(page.locator('#email')).toBeVisible({ timeout: 10_000 });
  await page.fill('#email', adminEmail || '');
  await page.fill('#password', adminPassword || '');
  await page.locator('button[type="submit"]').click();
  const dashboardVisible = await expect(page.locator('.view-dashboard.active'))
    .toBeVisible({ timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  if (!dashboardVisible) {
    const alertText = await page.locator('[role="alert"], .alert').last().textContent().catch(() => '');
    await page.fill('#password', '').catch(() => {});
    throw new Error(`登入失敗${alertText ? `:${alertText.trim()}` : ''}`);
  }
  await expect(page.locator('#today-composer-input')).toBeVisible({ timeout: 15_000 });
  await skipTour(page);
}

async function newAuthenticatedContext(browser, testInfo: TestInfo) {
  const projectContextOptions = contextOptionsForProject(testInfo);

  if (fs.existsSync(authStatePath)) {
    const cachedContext = await browser.newContext({
      ...projectContextOptions,
      storageState: authStatePath,
    });
    const cachedPage = await cachedContext.newPage();
    await cachedPage.goto('/');
    const isAuthenticated = await cachedPage.locator('.view-dashboard.active').isVisible({ timeout: 5_000 }).catch(() => false);
    // LibreChat may briefly render cached UI before refresh-token validation redirects to /login.
    // Keep the cached state only if it survives that auth refresh window.
    if (isAuthenticated) {
      await cachedPage.waitForLoadState('networkidle').catch(() => {});
      await cachedPage.waitForTimeout(1_000);
    }
    const stillAuthenticated = isAuthenticated
      && !/\/login(?:$|[?#])/.test(new URL(cachedPage.url()).pathname)
      && await cachedPage.locator('.brand-name').isVisible().catch(() => false);
    if (stillAuthenticated) {
      await skipTour(cachedPage);
      return { context: cachedContext, page: cachedPage };
    }
    await cachedContext.close();
    fs.rmSync(authStatePath, { force: true });
  }

  const context = await browser.newContext(projectContextOptions);
  const page = await context.newPage();
  await loginAsAdmin(page);
  await context.storageState({ path: authStatePath });
  return { context, page };
}

test.describe('承富 AI · 關鍵流程', () => {

  test('未登入 · 首頁必須導回登入頁', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
  });

});

test.describe.serial('承富 AI · 登入後關鍵流程', () => {
  let context: BrowserContext;
  let authPage: Page;

  test.beforeAll(async ({ browser }, testInfo) => {
    if (!hasAdminCredentials) {
      throw new Error('缺 E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD 或 Keychain E2E 憑證,不可跳過登入後主流程');
    }
    const session = await newAuthenticatedContext(browser, testInfo);
    context = session.context;
    authPage = session.page;
  });

  test.afterAll(async () => {
    await context?.close();
  });

  test('首頁 Launcher 載入工作台', async () => {
    const page = authPage;
    await page.goto('/');
    await expect(page.locator('#app')).toBeVisible({ timeout: 15_000 });
    await expect(page).toHaveTitle(/承富智慧助理|承富 AI/);
    await expect(page.locator('.brand-name')).toContainText('承富智慧助理');
    await expect(page.locator('.view-dashboard.active')).toBeVisible();
    await expect(page.locator('#today-composer-input')).toBeVisible();
    await expect(page.locator('#health-indicator')).toBeVisible();
    await expect(page.locator('#workspace-cards .workspace-card')).toHaveCount(5);
    await expect(page.locator('#tour-backdrop')).not.toHaveClass(/open/);
    await expect(page.locator('#tour-bubble')).not.toHaveClass(/open/);
  });

  test('Workspace · 5 個工作區可進入並帶入草稿', async () => {
    const page = authPage;
    await page.goto('/');
    await page.locator('#workspace-cards .workspace-card').first().click();
    await expect(page.locator('.view-workspace.active')).toBeVisible();
    await expect(page).toHaveURL(/#workspace-1/);
    await expect(page.locator('#workspace-title')).toContainText('投標工作區');
    await page.locator('#workspace-start-btn').click();
    await expect(page.locator('#chat-pane.open')).toBeVisible();
    await expect(page.locator('#chat-input')).toHaveValue(/投標工作區/);
  });

  test('今日輸入框 · L3 提醒 badge 會更新', async () => {
    const page = authPage;
    await page.goto('/');
    await expect(page.locator('#today-composer-input')).toBeVisible();
    await page.fill('#today-composer-input', '幫我分析選情,候選人策略要怎麼定');

    await page.locator('#today-composer-form button[type="submit"]').click();
    await expect(page.locator('#chat-pane.open')).toBeVisible();
    await expect(page.locator('#chat-input')).toHaveValue(/幫我分析選情/);
    await expect(page.locator('#chat-level-hint')).toContainText('第三級提醒', { timeout: 5_000 });
  });

  test('附件 · 選檔後顯示待送出 chip', async () => {
    const page = authPage;
    const tempFile = path.join(os.tmpdir(), `chengfu-e2e-attachment-${Date.now()}.txt`);
    fs.writeFileSync(tempFile, '承富附件 E2E 測試', 'utf8');
    try {
      await page.goto('/');
      await expect(page.locator('#app')).toBeVisible();
      await page.evaluate(() => window.chat?.open?.('00'));
      await expect(page.locator('#chat-pane.open')).toBeVisible({ timeout: 10_000 });
      await page.setInputFiles('#chat-file-input', tempFile);
      await expect(page.locator('.chat-attachment-chip')).toContainText('待送出');
      await expect(page.locator('.chat-attachment-chip')).toContainText(path.basename(tempFile));
    } finally {
      fs.rmSync(tempFile, { force: true });
    }
  });

  test('附件 · 可上傳並帶入 AI 送出 payload', async ({}, testInfo) => {
    // F-08 對應 · mobile chat pane SSE render 行為與桌機不同 · 桌機 PM happy-path 已驗附件主路徑
    test.skip(testInfo.project.name === 'mobile', '附件主路徑桌機已覆蓋,手機附件 SSE timing 另案');
    const page = authPage;
    const filename = `chengfu-e2e-upload-${Date.now()}.txt`;
    const tempFile = path.join(os.tmpdir(), filename);
    fs.writeFileSync(tempFile, '承富附件實際上傳測試', 'utf8');

    let chatPayloadHadFile = false;
    await page.route('**/api/agents/chat', async (route) => {
      const body = route.request().postDataJSON();
      chatPayloadHadFile = Array.isArray(body.files)
        && body.files.some((file) => String(file.filename || '').includes(filename));
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"text":"已收到附件"}\n\n',
      });
    });

    try {
      await page.goto('/');
      await page.locator('#workspace-cards .workspace-card').first().click();
      await page.locator('#workspace-start-btn').click();
      await page.setInputFiles('#chat-file-input', tempFile);
      await expect(page.locator('.chat-attachment-chip')).toContainText('待送出');
      await page.fill('#chat-input', '請閱讀附件並回覆收到');
      await page.locator('#chat-send-btn').click();
      await expect(page.locator('#chat-messages')).toContainText('已收到附件');
      expect(chatPayloadHadFile).toBeTruthy();
    } finally {
      fs.rmSync(tempFile, { force: true });
      await page.unroute('**/api/agents/chat').catch(() => {});
    }
  });

  test('PM happy-path · composer 到附件 AI 送出再複製交棒', async ({}, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', 'PM happy-path 已覆蓋桌機主路徑;手機另測導覽與附件基本能力');
    const page = authPage;
    const filename = `chengfu-e2e-pm-handoff-${Date.now()}.txt`;
    const tempFile = path.join(os.tmpdir(), filename);
    const pmPrompt = 'PM 請整理附件內容,產出設計交棒重點';
    fs.writeFileSync(tempFile, '活動主視覺需求: 需有 3 個方向,週五前交第一版。', 'utf8');

    let chatPayloadHadPrompt = false;
    let chatPayloadHadFile = false;
    await page.route('**/api/agents/chat', async (route) => {
      const body = route.request().postDataJSON();
      chatPayloadHadPrompt = String(body.message || body.text || '').includes(pmPrompt);
      chatPayloadHadFile = Array.isArray(body.files)
        && body.files.some((file) => String(file.filename || '').includes(filename));
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"text":"已整理成 PM 交棒重點: 目標、限制、素材與下一步。"}\n\n',
      });
    });

    try {
      await page.goto('/');
      await expect(page.locator('#today-composer-input')).toBeVisible();
      await page.fill('#today-composer-input', pmPrompt);
      await page.setInputFiles('#today-file-input', tempFile);
      await expect(page.locator('.today-file-chip')).toContainText(filename);
      await page.locator('#today-composer-form button[type="submit"]').click();
      await expect(page.locator('#chat-pane.open')).toBeVisible();
      await expect(page.locator('#chat-input')).toHaveValue(new RegExp(pmPrompt));
      await expect(page.locator('.chat-attachment-chip')).toContainText('待送出');
      await expect(page.locator('.chat-attachment-chip')).toContainText(filename);
      await page.locator('#chat-send-btn').click();
      await expect.poll(() => chatPayloadHadPrompt && chatPayloadHadFile, {
        message: 'chat payload should include today composer prompt and attachment metadata',
      }).toBeTruthy();

      await page.goto('/#projects');
      await expect(page.locator('.view-projects.active .project-card').first()).toBeVisible({ timeout: 10_000 });
      const handoffResponse = page.waitForResponse(resp =>
        resp.url().includes('/api-accounting/projects/') &&
        resp.url().includes('/handoff') &&
        resp.request().method() === 'GET'
      );
      await page.evaluate(() => {
        const projects = (window as any).Projects?.load?.() || [];
        const first = projects[0];
        if (!first) throw new Error('missing seeded project');
        (window as any).app.openProjectDrawer(first.id || first._id);
      });
      await expect(page.locator('#project-drawer.open')).toBeVisible();
      await handoffResponse.catch(() => {});

      await page.fill('#dr-goal', '完成第一版活動主視覺方向');
      await page.fill('#dr-constraints', '週五前交第一版\n不可使用簡體字');
      await page.fill('#dr-assets', `附件:${filename}`);
      await page.fill('#dr-next', '設計師產 3 個方向\nPM 依客戶回饋收斂');
      await page.evaluate(() => {
        (window as any).__copiedTexts = [];
        Object.defineProperty(navigator, 'clipboard', {
          configurable: true,
          value: {
            writeText: async (text: string) => {
              (window as any).__copiedTexts.push(text);
            },
          },
        });
      });

      await page.getByRole('button', { name: '複製 LINE' }).click();
      const handoffText = await page.evaluate(() => (window as any).__copiedTexts.at(-1));
      expect(handoffText).toContain('【工作包交棒】');
      expect(handoffText).toContain('完成第一版活動主視覺方向');
      expect(handoffText).toContain(filename);
      expect(handoffText).toContain('設計師產 3 個方向');
    } finally {
      fs.rmSync(tempFile, { force: true });
      await page.unroute('**/api/agents/chat').catch(() => {});
    }
  });

  test('Projects · 建立 · 看到卡片', async () => {
    const page = authPage;
    await page.goto('/#projects');
    await expect(page.locator('.view-projects.active')).toBeVisible();
    await expect(page.locator('.view-projects.active .project-card').first()).toBeVisible({ timeout: 10_000 });
  });

  test('工作包交棒卡 · 可複製 LINE / Email 格式', async () => {
    const page = authPage;
    await page.goto('/#projects');
    await expect(page.locator('.view-projects.active .project-card').first()).toBeVisible({ timeout: 10_000 });

    const handoffResponse = page.waitForResponse(resp =>
      resp.url().includes('/api-accounting/projects/') &&
      resp.url().includes('/handoff') &&
      resp.request().method() === 'GET'
    );
    await page.evaluate(() => {
      const projects = (window as any).Projects?.load?.() || [];
      const first = projects[0];
      if (!first) throw new Error('missing seeded project');
      (window as any).app.openProjectDrawer(first.id || first._id);
    });
    await expect(page.locator('#project-drawer.open')).toBeVisible();
    await handoffResponse.catch(() => {});

    await page.fill('#dr-goal', '完成第一版活動主視覺方向');
    await page.fill('#dr-constraints', '週五前要給客戶\n不可使用簡體字');
    await page.fill('#dr-assets', '內部資料夾/客戶/活動參考');
    await page.fill('#dr-next', '設計師產 3 個方向\nPM 整理客戶回饋');
    await page.evaluate(() => {
      (window as any).__copiedTexts = [];
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: async (text: string) => {
            (window as any).__copiedTexts.push(text);
          },
        },
      });
    });

    await page.getByRole('button', { name: '複製 LINE' }).click();
    const lineText = await page.evaluate(() => (window as any).__copiedTexts.at(-1));
    expect(lineText).toContain('【工作包交棒】');
    expect(lineText).toContain('完成第一版活動主視覺方向');
    expect(lineText).toContain('設計師產 3 個方向');

    await page.getByRole('button', { name: '複製 Email' }).click();
    const emailText = await page.evaluate(() => (window as any).__copiedTexts.at(-1));
    expect(emailText).toContain('主旨:');
    expect(emailText).toContain('工作包交棒');
    expect(emailText).toContain('需要我補資料的地方請直接回覆');
  });

  test('CRM Kanban · 8 階段列都在', async () => {
    const page = authPage;
    await page.goto('/#crm');
    await expect(page.locator('.view-crm.active')).toBeVisible();
    await expect(page.locator('.view-crm.active .kanban-col')).toHaveCount(8);
  });

  test('快捷鍵 ? · 開啟清單', async () => {
    const page = authPage;
    await page.goto('/');
    await expect(page.locator('#app')).toBeVisible();
    await page.keyboard.press('Escape');
    await page.locator('main').click();
    await page.keyboard.press('Shift+/');
    await expect(page.locator('.shortcuts.open')).toBeVisible();
  });

  test('Service Health · 指示器顯示', async () => {
    const page = authPage;
    await page.goto('/');
    await expect(page.locator('#health-indicator')).toBeVisible();
    // 需等 health check 跑完 · 容忍任何狀態
    const classes = await page.locator('#health-indicator').getAttribute('class');
    expect(classes).toMatch(/health-indicator (ok|warn|err)/);
  });

  test('會計 API · 載入儀表', async () => {
    const page = authPage;
    await page.goto('/#accounting');
    await expect(page.locator('.view-accounting.active')).toBeVisible();
    // 應顯示 4 個 stat-card(月收入/月支出/月淨利/逾 90 天)
    await expect(page.locator('.view-accounting.active .stat-card')).toHaveCount(4);
  });

  test('Mobile · 漢堡選單能打開', async ({ viewport }) => {
    test.skip(viewport?.width > 768, '只測手機尺寸');
    const page = authPage;
    await page.goto('/');
    await page.click('.mobile-menu-btn');
    await expect(page.locator('body.mobile-drawer-open .sidebar')).toBeVisible();
  });

  test('Mobile · 底部 5 工作區導覽正確', async ({ viewport }) => {
    test.skip(viewport?.width > 768, '只測手機尺寸');
    const page = authPage;
    await page.goto('/');
    for (const ws of ['1', '2', '3', '4', '5']) {
      await page.locator(`.mobile-bottom-item[data-ws="${ws}"]`).click();
      await expect(page.locator('.view-workspace.active')).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`#workspace-${ws}`));
      await expect(page.locator(`.mobile-bottom-item[data-ws="${ws}"]`)).toHaveClass(/active/);
    }
  });

});

test.describe('API 健康檢查', () => {
  test('LibreChat API', async ({ request }) => {
    const r = await request.get('/api/config');
    expect(r.ok()).toBeTruthy();
  });

  test('Accounting API healthz', async ({ request }) => {
    const r = await request.get('/api-accounting/healthz');
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.status).toBe('ok');
  });

  test('L3 classifier', async ({ request }) => {
    const safe = await request.post('/api-accounting/safety/classify', {
      data: { text: '幫我寫一則中秋節訊息' },
    });
    expect((await safe.json()).level).toBe('01');

    const risky = await request.post('/api-accounting/safety/classify', {
      data: { text: '幫我分析選情' },
    });
    expect((await risky.json()).level).toBe('03');
  });

  test('CRM stats', async ({ request, playwright }) => {
    const unauth = await request.get('/api-accounting/crm/stats');
    expect(unauth.status()).toBe(403);

    if (!hasAdminCredentials) {
      throw new Error('缺 E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD 或 Keychain E2E 憑證,不可跳過 authenticated API');
    }
    test.skip(!fs.existsSync(authStatePath), '需先跑登入後流程產生 session state');

    const authedRequest = await playwright.request.newContext({
      baseURL,
      storageState: authStatePath,
    });
    try {
      const r = await authedRequest.get('/api-accounting/crm/stats');
      expect(r.ok(), `authenticated CRM stats failed: HTTP ${r.status()}`).toBeTruthy();
    } finally {
      await authedRequest.dispose();
    }
  });
});
