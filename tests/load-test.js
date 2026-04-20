// ============================================================
// 承富 AI · k6 壓測腳本
// ============================================================
// 模擬 10 位同仁同時使用 · 驗證 Mac mini 24GB 撐得住尖峰
//
// 安裝:
//   brew install k6
//
// 執行:
//   k6 run tests/load-test.js
//
// 調整負載:
//   k6 run --vus 10 --duration 5m tests/load-test.js
//
// 預期:p95 < 3s, error rate < 1%

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ============================================================
// 配置
// ============================================================
const BASE_URL = __ENV.BASE_URL || 'http://localhost';

export const options = {
  scenarios: {
    // 承富 10 人日常使用
    chengfu_daily: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 3 },   // 早上開工,3 人陸續打開
        { duration: '2m',  target: 10 },  // 9:30 尖峰 · 全員上線
        { duration: '5m',  target: 10 },  // 持續尖峰
        { duration: '1m',  target: 3 },   // 午休,部分離線
        { duration: '30s', target: 0 },   // 結束
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<3000'],      // 95% 請求 < 3s
    http_req_failed:   ['rate<0.01'],       // 錯誤率 < 1%
    'group_duration{group:::Dashboard}':  ['p(95)<2000'],
    'group_duration{group:::Accounting}': ['p(95)<2000'],
  },
};

// ============================================================
// 測試場景
// ============================================================
export default function () {
  // 場景 1:承富 Launcher 首頁(讀取)
  group('Dashboard', () => {
    const res = http.get(`${BASE_URL}/`);
    check(res, { 'launcher 200': (r) => r.status === 200 });

    const cfg = http.get(`${BASE_URL}/api/config`);
    check(cfg, { 'libre cfg 200': (r) => r.status === 200 });
  });

  sleep(Math.random() * 2);

  // 場景 2:會計 API
  group('Accounting', () => {
    const health = http.get(`${BASE_URL}/api-accounting/healthz`);
    check(health, { 'accounting health': (r) => r.status === 200 });

    const accounts = http.get(`${BASE_URL}/api-accounting/accounts`);
    check(accounts, { 'accounts list': (r) => r.status === 200 });

    const dashboard = http.get(`${BASE_URL}/api-accounting/admin/dashboard`);
    check(dashboard, { 'admin dashboard': (r) => r.status === 200 });
  });

  sleep(Math.random() * 3);

  // 場景 3:Level 03 classifier(POST)
  group('Safety', () => {
    const r = http.post(
      `${BASE_URL}/api-accounting/safety/classify`,
      JSON.stringify({ text: '幫我寫一則中秋節祝賀' }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    check(r, {
      'classifier 200': (r) => r.status === 200,
      'classifier latency': (r) => r.timings.duration < 500,
    });
  });

  sleep(Math.random() * 5);

  // 場景 4:查專案 + 回饋
  group('Projects', () => {
    const projects = http.get(`${BASE_URL}/api-accounting/projects`);
    check(projects, { 'projects list': (r) => r.status === 200 });

    const feedback = http.get(`${BASE_URL}/api-accounting/feedback/stats`);
    check(feedback, { 'feedback stats': (r) => r.status === 200 });
  });

  sleep(Math.random() * 10 + 5);  // 模擬使用者閱讀 / 思考
}

// ============================================================
// 報告摘要
// ============================================================
export function handleSummary(data) {
  const pass = data.metrics.http_req_failed.values.rate < 0.01;
  const p95 = data.metrics.http_req_duration.values['p(95)'];

  console.log(`
╔══════════════════════════════════════════╗
║  承富壓測結果                                ║
╚══════════════════════════════════════════╝
  總請求數:${data.metrics.http_reqs.values.count}
  錯誤率:${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%
  p95 延遲:${p95.toFixed(0)}ms
  結論:${pass ? '✅ 通過(10 人併發下穩定)' : '❌ 失敗(需優化或升級硬體)'}
`);

  return {
    stdout: JSON.stringify(data, null, 2),
    'reports/load-test-latest.json': JSON.stringify(data, null, 2),
  };
}
