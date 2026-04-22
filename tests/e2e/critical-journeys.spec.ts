import { test, expect } from '@playwright/test';

/**
 * 承富 AI 關鍵 user journey
 *
 * 執行前提:
 *   1. docker compose up -d
 *   2. 跑過 seed-demo-data.py(有 3 專案 + 資料)
 *   3. 有 ADMIN 帳號:admin@chengfu.local / admin123
 */

test.describe('承富 AI · 關鍵流程', () => {

  test('首頁 Launcher 載入 · 看到 10 Agent', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/承富 AI/);
    // 等 app 載入(非 hidden)
    await expect(page.locator('#app')).toBeVisible({ timeout: 10_000 });
    // 確認品牌
    await expect(page.locator('.brand-name')).toContainText('承富 AI');
    // 確認 10 agent cards 存在(00 主管家 + 01-09)
    const agentCards = page.locator('.agent-card');
    await expect(agentCards).toHaveCount(10);
  });

  test('Hero 輸入框 · L3 警告(ROADMAP §11.13 真 assert)', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#app')).toBeVisible();
    await page.fill('#hero-input', '幫我分析選情,候選人策略要怎麼定');

    // 送出前 L3 classifier 應該跳 modal/dialog 警告
    // 兩種可能 UI · 任一觸發即視為通過:
    //   (a) window.confirm dialog
    //   (b) 自製 modal2-box(目前實作)
    const submitBtn = page.locator('.hero-submit').first();

    // Race · 任一條件先滿足都算通過
    const dialogPromise = page.waitForEvent('dialog', { timeout: 3000 }).catch(() => null);
    const modalPromise = page.locator('.modal2-box.open, [role="dialog"]')
      .first()
      .waitFor({ state: 'visible', timeout: 3000 })
      .then(() => 'modal')
      .catch(() => null);

    await submitBtn.click();

    const [dialogResult, modalResult] = await Promise.all([dialogPromise, modalPromise]);
    const triggered = !!dialogResult || !!modalResult;

    // 真 assert:必至少一個警告 UI 出現 · 不能靜默送出
    expect(triggered, 'L3 classifier 必觸發 dialog 或 modal 警告 · 不可靜默送出').toBe(true);

    // 若是 native dialog · 取消(避免阻塞後續 test)
    if (dialogResult) {
      await dialogResult.dismiss();
    }
  });

  test('Projects · 建立 · 看到卡片', async ({ page }) => {
    await page.goto('/#projects');
    await expect(page.locator('.view-projects')).toBeVisible();
    // 至少 seed 後應有 3 個
    await expect(page.locator('.project-card')).toHaveCount(3, { timeout: 5_000 });
  });

  test('CRM Kanban · 8 階段列都在', async ({ page }) => {
    await page.goto('/#crm');
    await expect(page.locator('.view-crm')).toBeVisible();
    await expect(page.locator('.kanban-col')).toHaveCount(8);
  });

  test('快捷鍵 ? · 開啟清單', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#app')).toBeVisible();
    await page.keyboard.press('?');
    await expect(page.locator('.shortcuts.open')).toBeVisible();
  });

  test('Service Health · 指示器顯示', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#app')).toBeVisible();
    await expect(page.locator('#health-indicator')).toBeVisible();
    // 需等 health check 跑完 · 容忍任何狀態
    const classes = await page.locator('#health-indicator').getAttribute('class');
    expect(classes).toMatch(/health-indicator (ok|warn|err)/);
  });

  test('會計 API · 載入儀表', async ({ page }) => {
    await page.goto('/#accounting');
    await expect(page.locator('.view-accounting')).toBeVisible();
    // 應顯示 4 個 stat-card(月收入/月支出/月淨利/逾 90 天)
    await expect(page.locator('.view-accounting .stat-card')).toHaveCount(4);
  });

  test('Mobile · 漢堡選單能打開', async ({ page, viewport }) => {
    test.skip(viewport?.width > 768, '只測手機尺寸');
    await page.goto('/');
    await expect(page.locator('#app')).toBeVisible();
    await page.click('.mobile-menu-btn');
    await expect(page.locator('body.mobile-drawer-open .sidebar')).toBeVisible();
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

  test('CRM stats', async ({ request }) => {
    const r = await request.get('/api-accounting/crm/stats');
    expect(r.ok()).toBeTruthy();
  });
});
