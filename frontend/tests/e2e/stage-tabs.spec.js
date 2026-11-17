import { expect, test } from '@playwright/test';

const CONFIG = {
  council_models: ['test/model-a', 'test/model-b'],
  chairman_model: 'test/chairman',
  web_search_enabled: false,
  defaults: {
    council_models: ['test/model-a', 'test/model-b'],
    chairman_model: 'test/chairman',
    web_search_enabled: false,
  },
};

const LONG_CONVERSATION = {
  id: 'conv-long',
  created_at: '2026-01-01T00:00:00.000Z',
  title: 'Long Council',
  messages: [
    { role: 'user', content: 'Compare the long council responses' },
    {
      role: 'assistant',
      stage1: [
        { model: 'test/model-a', response: 'Long answer A' },
        { model: 'test/model-b', response: 'Long answer B' },
      ],
      stage2: [
        { model: 'test/model-a', ranking: 'Long ranking A', parsed_ranking: [] },
        { model: 'test/model-b', ranking: 'Long ranking B', parsed_ranking: [] },
      ],
      stage3: { model: 'test/chairman', response: 'Long final answer' },
      metadata: {
        label_to_model: {},
        aggregate_rankings: [],
        status: 'complete',
      },
    },
  ],
};

const SHORT_CONVERSATION = {
  id: 'conv-short',
  created_at: '2026-01-02T00:00:00.000Z',
  title: 'Short Council',
  messages: [
    { role: 'user', content: 'Compare the short council response' },
    {
      role: 'assistant',
      stage1: [{ model: 'test/model-c', response: 'Short answer C' }],
      stage2: [{
        model: 'test/model-c',
        ranking: '{"findings":[{"claim":"Short ranking C"}],"final_ranking":["Response A"]}',
        review: { findings: [{ claim: 'Short ranking C' }], final_ranking: ['Response A'] },
        parsed_ranking: ['Response A'],
      }],
      stage3: { model: 'test/chairman', response: 'Short final answer' },
      metadata: {
        label_to_model: { 'Response A': 'test/model-c' },
        aggregate_rankings: [],
        status: 'complete',
      },
    },
  ],
};

const EMPTY_REVIEW_CONVERSATION = {
  ...SHORT_CONVERSATION,
  id: 'conv-empty-review',
  title: 'Empty Legacy Review',
  messages: [
    SHORT_CONVERSATION.messages[0],
    {
      ...SHORT_CONVERSATION.messages[1],
      stage2: [{
        ...SHORT_CONVERSATION.messages[1].stage2[0],
        ranking: JSON.stringify({ findings: [], final_ranking: ['Response A'] }),
        review: { findings: [], final_ranking: ['Response A'] },
      }],
    },
  ],
};

const FAILED_CONVERSATION = {
  id: 'conv-failed-reviews',
  created_at: '2026-01-03T00:00:00.000Z',
  title: 'Failed Reviews',
  messages: [
    { role: 'user', content: 'Review these candidates' },
    {
      role: 'assistant',
      stage1: LONG_CONVERSATION.messages[1].stage1,
      stage2: [],
      stage3: { model: 'test/chairman', response: 'Answer without reviews' },
      errors: {
        stage2: [
          { model: 'test/model-a', error_type: 'parse_failure', message: 'Invalid structured review' },
          { model: 'test/model-b', error_type: 'parse_failure', message: 'Invalid structured review' },
        ],
      },
      metadata: { label_to_model: {}, aggregate_rankings: [], status: 'complete' },
    },
  ],
};

const CONVERSATIONS = [LONG_CONVERSATION, SHORT_CONVERSATION, EMPTY_REVIEW_CONVERSATION, FAILED_CONVERSATION];

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function mockStageTabApi(page) {
  await page.route(/\/api\//, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();

    if (path === '/api/conversations' && method === 'GET') {
      return json(
        route,
        CONVERSATIONS.map((conversation) => ({
          id: conversation.id,
          created_at: conversation.created_at,
          title: conversation.title,
          message_count: conversation.messages.length,
        })),
      );
    }

    if (path === '/api/council/config' && method === 'GET') {
      return json(route, CONFIG);
    }

    const conversation = CONVERSATIONS.find((item) => path === `/api/conversations/${item.id}`);
    if (conversation && method === 'GET') {
      return json(route, conversation);
    }

    const config = CONVERSATIONS.find((item) => path === `/api/conversations/${item.id}/config`);
    if (config && method === 'GET') {
      return json(route, CONFIG);
    }

    return json(route, { detail: `Unhandled mock API route: ${method} ${path}` }, 500);
  });
}

test('stage tabs stay within the selected conversation results', async ({ page }) => {
  await mockStageTabApi(page);
  await page.goto('/');

  await page.getByText('Long Council', { exact: true }).click();
  const stage1 = page.locator('.stage1');
  const stage2 = page.locator('.stage2');

  // Stages 1–2 auto-collapse once the final answer lands; expand them,
  // and open Stage 2's collapsed raw-output disclosure.
  await stage1.getByRole('button', { name: 'Expand' }).click();
  await stage2.getByRole('button', { name: 'Expand' }).click();
  await stage2.getByText('Individual reviews').click();

  await expect(stage1.getByText('Long answer A')).toBeVisible();

  await stage1.getByRole('button', { name: 'model-b', exact: true }).click();
  await stage2.getByRole('button', { name: 'model-b', exact: true }).click();
  await expect(stage1.getByText('Long answer B')).toBeVisible();
  await expect(stage2.getByText('Long ranking B')).toBeVisible();

  await page.getByText('Short Council', { exact: true }).click();
  await stage1.getByRole('button', { name: 'Expand' }).click();
  await stage2.getByRole('button', { name: 'Expand' }).click();
  await stage2.getByText('Individual reviews').click();
  await expect(stage1.getByText('Short answer C')).toBeVisible();
  await expect(stage2.locator('.ranking-content')).toContainText('Short ranking C');
  await expect(stage2.locator('.parsed-ranking li')).toHaveText(['model-c']);
});

test('legacy empty findings keep their ranking without a JSON prose review', async ({ page }) => {
  await mockStageTabApi(page);
  await page.goto('/');
  await page.getByText('Empty Legacy Review', { exact: true }).click();
  const stage2 = page.locator('.stage2');
  await stage2.getByRole('button', { name: 'Expand' }).click();
  await stage2.getByText('Individual reviews (1)', { exact: true }).click();
  await expect(stage2.locator('.ranking-content')).toBeEmpty();
  await expect(stage2.locator('.ranking-content')).not.toContainText('final_ranking');
  await expect(stage2.locator('.parsed-ranking li')).toHaveText(['model-c']);
  await expect(stage2.locator('.tabs button')).toHaveCount(1);
});

test('all failed reviews remain visible without review tabs or a leaderboard', async ({ page }) => {
  await mockStageTabApi(page);
  await page.goto('/');
  await page.getByText('Failed Reviews', { exact: true }).click();
  const stage2 = page.locator('.stage2');
  await expect(stage2).toContainText('2 models queried, 0 successful, 2 failed');
  await stage2.getByRole('button', { name: 'Expand' }).click();
  await expect(stage2.locator('.error-item')).toHaveCount(2);
  await expect(stage2.getByText('Invalid structured review', { exact: true })).toHaveCount(2);
  await expect(stage2.locator('.tabs')).toHaveCount(0);
  await expect(stage2.locator('.aggregate-rankings')).toHaveCount(0);
  await expect(page.getByText('Answer without reviews', { exact: true })).toBeVisible();
});
