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

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function mockVoiceApi(page, { transcriptionText = 'transcribed words' } = {}) {
  await page.route(/\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();

    if (path === '/api/conversations' && method === 'GET') {
      return json(route, []);
    }
    if (path === '/api/council/config' && method === 'GET') {
      return json(route, CONFIG);
    }
    if (path === '/api/transcribe' && method === 'POST') {
      return json(route, { text: transcriptionText });
    }
    return json(route, { detail: `Unhandled mock API route: ${method} ${path}` }, 500);
  });
}

test('failed recorder setup releases the microphone stream', async ({ page }) => {
  await mockVoiceApi(page);
  await page.addInitScript(() => {
    window.__trackStops = 0;
    const track = {
      kind: 'audio',
      stop() {
        window.__trackStops += 1;
      },
    };
    const stream = { getTracks: () => [track] };
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: async () => stream },
    });
    Object.defineProperty(window, 'MediaRecorder', {
      configurable: true,
      writable: true,
      value: class {
        static isTypeSupported() {
          return true;
        }
        constructor() {
          throw new Error('recorder unavailable');
        }
      },
    });
  });

  await page.goto('/');
  await page.getByLabel('Start voice dictation').click();

  await expect(page.getByText('Failed to access microphone')).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.__trackStops)).toBe(1);
});

test('recording uses a local session and transcribes on stop', async ({ page }) => {
  await mockVoiceApi(page);
  await page.addInitScript(() => {
    window.__trackStops = 0;
    const track = {
      kind: 'audio',
      stop() {
        window.__trackStops += 1;
      },
    };
    const stream = { getTracks: () => [track] };
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: async () => stream },
    });
    Object.defineProperty(window, 'MediaRecorder', {
      configurable: true,
      writable: true,
      value: class {
        static isTypeSupported() {
          return true;
        }
        constructor(stream, options) {
          this.stream = stream;
          this.mimeType = options?.mimeType || 'audio/webm';
          this.state = 'inactive';
          this.ondataavailable = null;
          this.onstop = null;
        }
        start() {
          this.state = 'recording';
        }
        stop() {
          if (this.state !== 'recording') {
            throw new Error('MediaRecorder is not recording');
          }
          this.state = 'inactive';
          this.ondataavailable?.({
            data: new Blob(['audio'], { type: this.mimeType }),
          });
          setTimeout(() => this.onstop?.(), 0);
        }
      },
    });
  });

  await page.goto('/');
  const voiceButton = page.getByLabel('Start voice dictation');
  await voiceButton.click();
  await expect(page.getByLabel('Stop recording')).toBeVisible();

  await page.getByLabel('Stop recording').click();
  await expect(page.getByPlaceholder('Ask your question...')).toHaveValue(
    'transcribed words',
  );
  await expect.poll(() => page.evaluate(() => window.__trackStops)).toBe(1);
});
