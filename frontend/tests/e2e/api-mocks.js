const CONVERSATION_ID = 'conv-e2e';
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

const STAGE1 = [
  { model: 'test/model-a', response: 'Candidate answer from model A' },
  { model: 'test/model-b', response: 'Candidate answer from model B' },
];

const STAGE2 = [
  {
    model: 'test/model-a',
    ranking: '{"findings": [], "final_ranking": ["Response A", "Response B"]}',
    parsed_ranking: ['Response A', 'Response B'],
  },
  {
    model: 'test/model-b',
    ranking: '{"findings": [], "final_ranking": ["Response B", "Response A"]}',
    parsed_ranking: ['Response B', 'Response A'],
  },
];

const STAGE2_METADATA = {
  label_to_model: {
    'Response A': 'test/model-a',
    'Response B': 'test/model-b',
  },
  aggregate_rankings: [
    { model: 'test/model-a', average_rank: 1.5, rankings_count: 2 },
    { model: 'test/model-b', average_rank: 1.5, rankings_count: 2 },
  ],
  tournament_rankings: [],
};

function conversation(messages = []) {
  return {
    id: CONVERSATION_ID,
    created_at: '2026-01-01T00:00:00.000Z',
    title: 'New Conversation',
    messages,
  };
}

function councilEvents() {
  return [
    { type: 'stage1_start' },
    { type: 'stage1_complete', data: STAGE1, errors: [] },
    { type: 'stage2_start' },
    {
      type: 'stage2_complete',
      data: STAGE2,
      errors: [],
      metadata: STAGE2_METADATA,
    },
    { type: 'stage3_start' },
    {
      type: 'stage3_complete',
      data: { model: 'test/chairman', response: 'Council final answer' },
      errors: [],
      metadata: { status: 'complete' },
    },
    { type: 'complete' },
  ];
}

function chairmanEvents() {
  return [
    { type: 'chairman_start' },
    {
      type: 'chairman_complete',
      data: { model: 'test/chairman', response: 'Chairman direct answer' },
      errors: null,
    },
    { type: 'complete' },
  ];
}

function sse(events) {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
}

function assistantMessage(mode) {
  if (mode === 'chairman') {
    return {
      role: 'assistant',
      mode: 'chairman',
      stage1: null,
      stage2: null,
      stage3: { model: 'test/chairman', response: 'Chairman direct answer' },
    };
  }

  return {
    role: 'assistant',
    stage1: STAGE1,
    stage2: STAGE2,
    stage3: { model: 'test/chairman', response: 'Council final answer' },
    metadata: {
      label_to_model: STAGE2_METADATA.label_to_model,
      aggregate_rankings: STAGE2_METADATA.aggregate_rankings,
      prompt_version: 'evidence-v1',
      status: 'complete',
    },
  };
}

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

export async function mockCouncilApi(page) {
  let completed = false;
  let lastMode = 'council';
  let lastContent = '';

  await page.route(/\/api\//, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();

    if (path === '/api/conversations' && method === 'GET') {
      return json(
        route,
        completed
          ? [
              {
                id: CONVERSATION_ID,
                created_at: '2026-01-01T00:00:00.000Z',
                title: 'New Conversation',
                message_count: 2,
              },
            ]
          : [],
      );
    }

    if (path === '/api/conversations' && method === 'POST') {
      return json(route, conversation());
    }

    if (path === '/api/council/config' && method === 'GET') {
      return json(route, CONFIG);
    }

    if (path === `/api/conversations/${CONVERSATION_ID}` && method === 'GET') {
      if (!completed) {
        return json(route, conversation());
      }
      return json(
        route,
        conversation([
          { role: 'user', content: lastContent },
          assistantMessage(lastMode),
        ]),
      );
    }

    if (path === `/api/conversations/${CONVERSATION_ID}/config` && method === 'GET') {
      return json(route, CONFIG);
    }

    if (path === '/api/models' && method === 'GET') {
      return json(route, { providers: [], total_models: 0 });
    }

    if (path.endsWith('/message/stream') && method === 'POST') {
      const payload = request.postDataJSON();
      lastMode = payload.mode || 'council';
      lastContent = payload.content || '';
      completed = true;
      const events = lastMode === 'chairman' ? chairmanEvents() : councilEvents();
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        headers: { 'Cache-Control': 'no-cache' },
        body: sse(events),
      });
    }

    return json(route, { detail: `Unhandled mock API route: ${method} ${path}` }, 500);
  });
}
