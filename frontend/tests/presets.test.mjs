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

test('presets use the November 2026 model lineup', () => {
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
  assert.ok(modelIds.includes('openai/gpt-6.1-sol'));
  assert.ok(modelIds.includes('google/gemini-4-argon'));
  assert.ok(modelIds.includes('google/gemini-3.8-flash'));
  assert.ok(!modelIds.includes('google/gemini-3.5-flash-lite'));
  assert.ok(modelIds.includes('anthropic/claude-haiku-5.5'));
  assert.ok(modelIds.includes('minimax/minimax-m3.1-flash'));
  assert.ok(modelIds.includes('moonshotai/kimi-k3.1-pro'));
  assert.ok(modelIds.includes('deepseek/deepseek-v4.1-flash-1017'));
  assert.ok(modelIds.includes('nvidia/nemotron-3.5-super-vl'));
});

test('balanced, budget, and speed presets use role-aligned current models', () => {
  const balanced = MODEL_PRESETS.find((preset) => preset.id === 'balanced');
  const budget = MODEL_PRESETS.find((preset) => preset.id === 'budget');
  const largeCouncil = MODEL_PRESETS.find((preset) => preset.id === 'large-council');
  const speed = MODEL_PRESETS.find((preset) => preset.id === 'speed');

  assert.ok(balanced, 'expected balanced preset to exist');
  assert.ok(budget, 'expected budget preset to exist');
  assert.ok(largeCouncil, 'expected large council preset to exist');
  assert.ok(speed, 'expected speed preset to exist');
  assert.ok(balanced.council_models.includes('openai/gpt-6.1-sol'));
  assert.ok(!balanced.council_models.includes('openai/gpt-6.1-terra'));
  assert.ok(budget.council_models.includes('nvidia/nemotron-3.5-super-vl'));
  assert.ok(!budget.council_models.includes('nvidia/nemotron-3-ultra-550b-a55b'));
  assert.ok(largeCouncil.council_models.includes('nvidia/nemotron-3-ultra-550b-a55b'));

  assert.ok(speed.council_models.includes('google/gemini-3.8-flash'));
  assert.ok(!speed.council_models.includes('google/gemini-3.5-flash-lite'));
  assert.equal(speed.chairman_model, 'google/gemini-3.8-flash');

  for (const preset of [budget, speed]) {
    assert.ok(preset.council_models.includes('anthropic/claude-haiku-5.5'));
    assert.ok(!preset.council_models.includes('anthropic/claude-haiku-4.5'));
  }
});

test('flagship preset does not include deepseek', () => {
  const flagship = MODEL_PRESETS.find((preset) => preset.id === 'flagship');

  assert.ok(flagship, 'expected flagship preset to exist');
  assert.ok(
    !flagship.council_models.some((modelId) => modelId.startsWith('deepseek/')),
    'did not expect flagship preset to include a deepseek model'
  );

  const budget = MODEL_PRESETS.find((preset) => preset.id === 'budget');

  assert.ok(budget, 'expected budget preset to exist');
  assert.ok(
    budget.council_models.includes('deepseek/deepseek-v4.1-flash-1017'),
    'expected budget preset to include the latest DeepSeek Flash model'
  );
});
