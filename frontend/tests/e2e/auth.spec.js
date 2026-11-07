import { expect, test } from '@playwright/test';

const TOKEN = 'e2e-api-token';

async function mockAuthenticatedApi(page, seenAuthHeaders) {
  await page.route(/\/api\//, async (route) => {
    const auth = route.request().headers()['authorization'] || null;
    seenAuthHeaders.push(auth);
    if (auth !== `Bearer ${TOKEN}`) {
      return route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Missing or invalid API token' }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

test('prompts for the API token on 401 and retries with it', async ({ page }) => {
  const seen = [];
  await mockAuthenticatedApi(page, seen);
  page.on('dialog', (dialog) => dialog.accept(TOKEN));

  await page.goto('/');

  await expect.poll(() => seen.includes(`Bearer ${TOKEN}`)).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem('llmCouncilApiToken'))).toBe(TOKEN);
});

test('captures ?token= from the URL and strips it', async ({ page }) => {
  const seen = [];
  await mockAuthenticatedApi(page, seen);
  let prompted = false;
  page.on('dialog', (dialog) => {
    prompted = true;
    dialog.dismiss();
  });

  await page.goto(`/?token=${TOKEN}`);

  await expect.poll(() => seen.length).toBeGreaterThan(0);
  expect(seen.every((auth) => auth === `Bearer ${TOKEN}`)).toBe(true);
  expect(prompted).toBe(false);
  expect(new URL(page.url()).searchParams.has('token')).toBe(false);
});
