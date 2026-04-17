import test from 'node:test';
import assert from 'node:assert/strict';

import { MODEL_PRESETS } from '../src/presets.js';

test('presets do not reference retired Grok 4.20 beta model ids', () => {
  const modelIds = MODEL_PRESETS.flatMap((preset) => [
    ...preset.council_models,
    preset.chairman_model,
  ]);

  assert.ok(
    modelIds.includes('x-ai/grok-4.20-multi-agent'),
    'expected presets to use x-ai/grok-4.20-multi-agent'
  );
  assert.ok(
    !modelIds.includes('x-ai/grok-4.20-multi-agent-beta'),
    'did not expect retired x-ai/grok-4.20-multi-agent-beta'
  );
});

test('flagship preset does not include deepseek', () => {
  const flagship = MODEL_PRESETS.find((preset) => preset.id === 'flagship');

  assert.ok(flagship, 'expected flagship preset to exist');
  assert.ok(
    !flagship.council_models.includes('deepseek/deepseek-v3.2-speciale'),
    'did not expect flagship preset to include deepseek/deepseek-v3.2-speciale'
  );
});
