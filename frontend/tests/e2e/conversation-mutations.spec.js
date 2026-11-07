import { expect, test } from '@playwright/test';

const CONFIG = {
  council_models: ['test/model-a'],
  chairman_model: 'test/chairman',
  web_search_enabled: false,
  defaults: {
    council_models: ['test/model-a'],
    chairman_model: 'test/chairman',
    web_search_enabled: false,
  },
};

const CONVERSATION = {
  id: 'conv-mutable',
  created_at: '2026-01-01T00:00:00.000Z',
  title: 'Mutable Conversation',
  messages: [{ role: 'user', content: 'Existing question' }],
};

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

test('composer locks while a conversation mutation is in flight', async ({ page }) => {
  await page.route(/\/api\//, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();

    if (path === '/api/conversations' && method === 'GET') {
      return json(route, [
        {
          id: CONVERSATION.id,
          created_at: CONVERSATION.created_at,
          title: CONVERSATION.title,
          message_count: CONVERSATION.messages.length,
        },
      ]);
    }

    if (path === `/api/conversations/${CONVERSATION.id}` && method === 'GET') {
      return json(route, CONVERSATION);
    }

    if (path === `/api/conversations/${CONVERSATION.id}/config` && method === 'GET') {
      return json(route, CONFIG);
    }

    if (path === '/api/council/config' && method === 'GET') {
      return json(route, CONFIG);
    }

    if (path === `/api/conversations/${CONVERSATION.id}` && method === 'DELETE') {
      await new Promise((resolve) => setTimeout(resolve, 250));
      return json(route, { status: 'ok' });
    }

    return json(route, { detail: `Unhandled mock API route: ${method} ${path}` }, 500);
  });

  page.on('dialog', (dialog) => dialog.accept());
  await page.goto('/');

  await page.getByText('Mutable Conversation', { exact: true }).click();
  await expect(page.getByText('Existing question')).toBeVisible();
  await page.getByPlaceholder('Ask a follow-up question...').fill('Pending send');
  await expect(page.locator('.send-button-icon')).toBeEnabled();

  await page.getByLabel('Delete conversation Mutable Conversation').click();
  await expect(page.locator('.send-button-icon')).toBeDisabled();

  await expect(page.getByPlaceholder('Ask your question...')).toBeVisible();
});
