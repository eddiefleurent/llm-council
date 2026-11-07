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
      stage2: [{ model: 'test/model-c', ranking: 'Short ranking C', parsed_ranking: [] }],
      stage3: { model: 'test/chairman', response: 'Short final answer' },
      metadata: {
        label_to_model: {},
        aggregate_rankings: [],
        status: 'complete',
      },
    },
  ],
};

const CONVERSATIONS = [LONG_CONVERSATION, SHORT_CONVERSATION];

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
  await expect(stage1.getByText('Long answer A')).toBeVisible();

  await stage1.getByRole('button', { name: 'model-b', exact: true }).click();
  await stage2.getByRole('button', { name: 'model-b', exact: true }).click();
  await expect(stage1.getByText('Long answer B')).toBeVisible();

  await page.getByText('Short Council', { exact: true }).click();
  await expect(stage1.getByText('Short answer C')).toBeVisible();
  await expect(stage2.getByText('Short ranking C')).toBeVisible();
});
