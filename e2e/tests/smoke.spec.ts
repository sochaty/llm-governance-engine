import { test, expect } from '@playwright/test';

// ── Navigation shell ──────────────────────────────────────────────────────────

test('root redirects to dashboard', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/dashboard/);
});

test('app nav bar is visible', async ({ page }) => {
  await page.goto('/');
  const nav = page.locator('nav');
  await expect(nav).toBeVisible();
});

// ── Dashboard ─────────────────────────────────────────────────────────────────

test('dashboard renders heading and stats strip', async ({ page }) => {
  await page.goto('/dashboard');

  // Main heading
  await expect(page.locator('h1')).toContainText('Governance Insights');

  // Stats strip — four stat cards should be present
  const statItems = page.locator('.stat-item');
  await expect(statItems).toHaveCount(4);
});

test('dashboard shows benchmark input area', async ({ page }) => {
  await page.goto('/dashboard');

  // Textarea for prompt input
  await expect(page.locator('textarea')).toBeVisible();

  // Run Benchmark button
  await expect(page.locator('button.run-btn')).toBeVisible();
  await expect(page.locator('button.run-btn')).toContainText('Run Benchmark');
});

test('dashboard run button is disabled when prompt is empty', async ({ page }) => {
  await page.goto('/dashboard');
  const runBtn = page.locator('button.run-btn');
  await expect(runBtn).toBeDisabled();
});

test('dashboard run button enables after typing a prompt', async ({ page }) => {
  await page.goto('/dashboard');
  await page.locator('textarea').fill('What is the capital of France?');
  const runBtn = page.locator('button.run-btn');
  await expect(runBtn).toBeEnabled();
});

test('dashboard has cloud and local response cards', async ({ page }) => {
  await page.goto('/dashboard');
  // Two comparison cards — frontier (cloud) and local
  await expect(page.locator('.card.frontier')).toBeVisible();
  await expect(page.locator('.card.local')).toBeVisible();
});

test('dashboard radar chart canvas is present', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.locator('canvas[baseChart]')).toBeVisible();
});

// ── Audit Vault ───────────────────────────────────────────────────────────────

test('audit vault page loads via nav', async ({ page }) => {
  await page.goto('/');
  await page.locator('a', { hasText: 'Audit Vault' }).click();
  await expect(page).toHaveURL(/history/);
  await expect(page.locator('h1')).toContainText('Audit Vault');
});

test('audit vault shows empty state when no records', async ({ page }) => {
  await page.goto('/history');
  // Either the table or the empty-state message should be visible
  const hasEmptyState = await page.locator('.empty-state').isVisible();
  const hasTable = await page.locator('table').isVisible();
  expect(hasEmptyState || hasTable).toBeTruthy();
});

// ── Settings ──────────────────────────────────────────────────────────────────

test('settings page loads via nav', async ({ page }) => {
  await page.goto('/');
  await page.locator('a', { hasText: 'Settings' }).click();
  await expect(page).toHaveURL(/settings/);
});

test('settings page shows settings container and sections', async ({ page }) => {
  await page.goto('/settings');
  await expect(page.locator('.settings-container')).toBeVisible();
  // Four sections: cloud, local, governance, models
  const sections = page.locator('.settings-section');
  await expect(sections).toHaveCount(4);
});

// ── API connectivity (backend reachable) ─────────────────────────────────────

test('backend health endpoint returns healthy', async ({ request }) => {
  // Direct API call — verifies the backend is responding
  const response = await request.get('http://localhost:8000/api/health');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.status).toBe('healthy');
});

test('settings API returns all known keys', async ({ request }) => {
  const response = await request.get('http://localhost:8000/api/v1/settings');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.settings).toHaveLength(10);
});

test('cloud providers API returns 4 providers', async ({ request }) => {
  const response = await request.get('http://localhost:8000/api/v1/models/cloud');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.providers).toHaveLength(4);
});
