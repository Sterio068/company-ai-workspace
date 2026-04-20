import { defineConfig, devices } from '@playwright/test';

/**
 * 承富 AI E2E 測試 · Playwright
 *
 * 安裝:
 *   npx playwright install chromium
 *   npm install --save-dev @playwright/test
 *
 * 執行:
 *   npx playwright test
 *
 * 首次需本機已啟動(docker compose up)
 */
export default defineConfig({
  testDir: './.',
  timeout: 30_000,
  fullyParallel: false,

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    locale: 'zh-TW',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile',   use: { ...devices['iPhone 13'] } },
  ],

  webServer: process.env.CI ? undefined : {
    command: 'echo "需先 docker compose up · 否則測試會失敗"',
    url: 'http://localhost',
    reuseExistingServer: true,
  },
});
