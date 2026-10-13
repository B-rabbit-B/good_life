import { defineConfig, devices } from '@playwright/test'

const layout = { ...devices['Desktop Chrome'], isMobile: true, hasTouch: true }

export default defineConfig({
  outputDir: 'test-results',
  workers: 1, // 全部测试共用一个测试库
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'node scripts/e2e-server.mjs',
    url: 'http://127.0.0.1:8765/api/health',
    reuseExistingServer: false,
    timeout: 240_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
  projects: [
    { name: 'iphone-13', testDir: 'e2e/acceptance', use: { ...devices['iPhone 13'] } },
    { name: 'pixel-7', testDir: 'e2e/acceptance', use: { ...devices['Pixel 7'] } },
    { name: 'layout-390', testDir: 'e2e/pages', use: { ...layout, viewport: { width: 390, height: 844 } } },
    { name: 'layout-360', testDir: 'e2e/pages', use: { ...layout, viewport: { width: 360, height: 800 } } },
    { name: 'visual', testDir: 'e2e/visual', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } } },
  ],
})
