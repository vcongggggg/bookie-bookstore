// @ts-check
const { defineConfig, devices } = require('@playwright/test');

const baseURL = process.env.BOOKIE_BASE_URL || 'http://127.0.0.1:8000';

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:DEBUG=\'True\'; python manage.py migrate --noinput; python manage.py seed_fake_data --reset-demo; python manage.py runserver 127.0.0.1:8000"',
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['Pixel 7'] },
    },
  ],
});
