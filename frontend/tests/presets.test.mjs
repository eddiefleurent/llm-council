import test from 'node:test';
import assert from 'node:assert/strict';

import { MODEL_PRESETS } from '../src/presets.js';

const RETIRED_FROM_PRESETS = [
  'x-ai/grok-4.20-multi-agent',
  'x-ai/grok-4.20-multi-agent-beta',
  'x-ai/grok-4.1-fast',
  'anthropic/claude-opus-4.6',
  'anthropic/claude-sonnet-4.6',
  'openai/gpt-5.4',
  'openai/gpt-5.4-mini',
  'moonshotai/kimi-k2.5',
  'z-ai/glm-5',
  'google/gemini-3-flash-preview',
  'google/gemini-3.1-flash-lite-preview',
  'minimax/minimax-m2.7',
  'nvidia/nemotron-3-super-120b-a12b',
];

test('presets use the October 2026 model lineup', () => {
  const modelIds = MODEL_PRESETS.flatMap((preset) => [
    ...preset.council_models,
    preset.chairman_model,
  ]);

  for (const retired of RETIRED_FROM_PRESETS) {
    assert.ok(!modelIds.includes(retired), `did not expect retired ${retired}`);
  }

  assert.ok(modelIds.includes('x-ai/grok-4.7'));
  assert.ok(modelIds.includes('anthropic/claude-opus-5.5'));
  assert.ok(modelIds.includes('openai/gpt-6-astra'));
  assert.ok(modelIds.includes('openai/gpt-6-luna'));
});

test('flagship preset does not include deepseek', () => {
  const flagship = MODEL_PRESETS.find((preset) => preset.id === 'flagship');

  assert.ok(flagship, 'expected flagship preset to exist');
  assert.ok(
    !flagship.council_models.some((modelId) => modelId.startsWith('deepseek/')),
    'did not expect flagship preset to include a deepseek model'
  );
});
