import { expect, test } from '@playwright/test';

import { mockCouncilApi } from './api-mocks.js';

test.beforeEach(async ({ page }) => {
  await mockCouncilApi(page);
  await page.goto('/');
});

test('council response renders all three stages', async ({ page }) => {
  await page.getByPlaceholder('Ask your question...').fill('Compare caching strategies');
  await page.getByRole('button', { name: 'Send message' }).click();

  await expect(page.getByText('Stage 1: Individual Responses')).toBeVisible();
  await expect(page.getByText('Stage 2: Evidence Review')).toBeVisible();
  await expect(page.getByText('Final Council Answer')).toBeVisible();
  await expect(page.getByText('Council final answer')).toBeVisible();
  await expect(page.getByText('Compare caching strategies')).toBeVisible();
});

test('chairman mode renders a direct chairman response', async ({ page }) => {
  await page.getByRole('button', { name: 'Chairman', exact: true }).click();
  await page.getByPlaceholder('Chat with the chairman...').fill('Make it shorter');
  await page.getByRole('button', { name: 'Send message' }).click();

  await expect(page.getByText('Chairman Direct', { exact: true })).toBeVisible();
  await expect(page.getByText('Chairman Response', { exact: true })).toBeVisible();
  await expect(page.getByText('Chairman direct answer')).toBeVisible();
  await expect(page.getByText('Stage 1: Individual Responses')).toHaveCount(0);
});

test('reviews render readable evaluations, citations, and complete rankings after reload', async ({ page }) => {
  await page.getByPlaceholder('Ask your question...').fill('Compare caching strategies');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Council final answer')).toBeVisible();

  // Check both the streamed result and the persisted conversation shape.
  for (const reload of [false, true]) {
    if (reload) await page.reload();
    const stage2 = page.locator('.stage2');
    await stage2.getByRole('button', { name: 'Expand' }).click();
    await stage2.getByText('Individual reviews (2)', { exact: true }).click();
    await expect(stage2.locator('.ranking-content')).toContainText('model-a gives the clearest supported answer.');
    await expect(stage2.locator('.ranking-content strong')).toHaveText(['model-a', 'supported answer']);
    await expect(stage2.getByRole('link', { name: 'Source' })).toHaveAttribute('href', 'https://example.com/evidence');
    await expect(stage2.locator('.ranking-content')).not.toContainText('final_ranking');
    await expect(stage2.locator('.parsed-ranking li')).toHaveText(['model-a', 'model-b']);
    await expect(stage2.locator('.rank-count')).toHaveText(['(2 votes)', '(2 votes)']);

    await stage2.getByRole('button', { name: 'model-b', exact: true }).click();
    await expect(stage2.locator('.ranking-content')).toHaveText('model-b preserves the budget constraint.');
    await expect(stage2.locator('.parsed-ranking li')).toHaveText(['model-b', 'model-a']);
  }
});

test('configuration modal opens with quick presets', async ({ page }) => {
  await page
    .getByRole('button', { name: 'Configure models for this conversation' })
    .click();

  await expect(page.getByRole('heading', { name: 'Configure New Conversation' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Quick Presets' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Flagship/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Budget/ })).toBeVisible();

  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Configure New Conversation' })).toHaveCount(0);
});
