<template>
  <div class="model-selector" :class="{ expanded: isOpen }">
    <!-- Compact badge (always visible) -->
    <button class="model-badge-btn" @click="toggleOpen" :disabled="modelState.loading">
      <span class="badge-dot" :class="statusDotClass"></span>
      <span class="badge-label">{{ activeLabel }}</span>
      <span class="badge-arrow">{{ isOpen ? '&#9650;' : '&#9660;' }}</span>
    </button>

    <!-- Dropdown panel -->
    <div v-if="isOpen" class="dropdown-panel" @click.stop>
      <div class="dropdown-header">
        <span class="dropdown-title">Select AI Model</span>
        <button class="close-btn" @click="isOpen = false">&times;</button>
      </div>

      <!-- Tab bar: Global / Per-Step -->
      <div class="tab-bar">
        <button class="tab-btn" :class="{ active: activeTab === 'global' }" @click="activeTab = 'global'">Global</button>
        <button class="tab-btn" :class="{ active: activeTab === 'steps' }" @click="activeTab = 'steps'; loadStepOverrides()">Per-Step</button>
      </div>

      <!-- Loading state -->
      <div v-if="modelState.loading" class="dropdown-loading">
        Loading models...
      </div>

      <!-- GLOBAL TAB -->
      <template v-if="activeTab === 'global' && !modelState.loading">
        <!-- Provider list -->
        <div class="provider-list">
          <div
            v-for="provider in modelState.providers"
            :key="provider.id"
            class="provider-group"
          >
            <div class="provider-header">
              <span class="provider-dot" :class="provider.api_key_configured ? 'dot-green' : 'dot-red'"></span>
              <span class="provider-name">{{ provider.name }}</span>
              <span class="provider-type">{{ provider.type }}</span>
            </div>

            <div v-if="!provider.api_key_configured && provider.type === 'cloud'" class="provider-disabled">
              API key not configured
            </div>

            <div v-else class="model-list">
              <button
                v-for="model in provider.models"
                :key="model.id"
                class="model-item"
                :class="{
                  active: modelState.active.provider_id === provider.id && modelState.active.model_name === model.id,
                  testing: testingModel === `${provider.id}/${model.id}`,
                }"
                @click="handleSelect(provider, model)"
              >
                <span class="model-name">{{ model.name || model.id }}</span>
                <span class="model-cost" v-if="costCache[`${provider.id}/${model.id}`]">
                  {{ formatCost(costCache[`${provider.id}/${model.id}`]) }}
                </span>
                <span
                  v-if="modelState.active.provider_id === provider.id && modelState.active.model_name === model.id"
                  class="active-check"
                >&#10003;</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="dropdown-footer">
          <button
            class="test-btn"
            :disabled="!modelState.active.model_name || modelState.testing"
            @click="handleTest"
          >
            {{ modelState.testing ? 'Testing...' : 'Test Connection' }}
          </button>
          <div v-if="modelState.testResult" class="test-result" :class="modelState.testResult.status">
            <template v-if="modelState.testResult.status === 'ok'">
              OK ({{ modelState.testResult.latency_ms }}ms)
            </template>
            <template v-else>
              {{ modelState.testResult.error || 'Failed' }}
            </template>
          </div>

          <!-- Model performance stats -->
          <div v-if="modelStats[modelState.active.model_name]" class="model-stats">
            <div class="stat-label">Performance:</div>
            <div class="stat-value">
              {{ modelStats[modelState.active.model_name].calls }} calls,
              {{ modelStats[modelState.active.model_name].avg_latency_ms }}ms avg
            </div>
          </div>
        </div>
      </template>

      <!-- PER-STEP TAB -->
      <template v-if="activeTab === 'steps' && !modelState.loading">
        <div class="step-list">
          <div v-for="step in stepOverrides.steps" :key="step" class="step-row">
            <div class="step-info">
              <span class="step-name-label">{{ stepLabels[step] || step }}</span>
              <span class="step-model">
                {{ stepOverrides.step_overrides[step]
                  ? `${stepOverrides.step_overrides[step].provider_id} / ${stepOverrides.step_overrides[step].model_name}`
                  : 'Global default' }}
              </span>
            </div>
            <div class="step-actions">
              <select
                class="step-select"
                :value="stepSelectValue(step)"
                @change="handleStepChange(step, $event)"
              >
                <option value="">Global default</option>
                <optgroup v-for="provider in modelState.providers" :key="provider.id" :label="provider.name">
                  <option
                    v-for="model in provider.models"
                    :key="model.id"
                    :value="`${provider.id}|${model.id}|${provider.base_url}`"
                    :disabled="!provider.api_key_configured && provider.type === 'cloud'"
                  >{{ model.name || model.id }}</option>
                </optgroup>
              </select>
            </div>
          </div>
        </div>
      </template>

      <!-- Error display -->
      <div v-if="modelState.error" class="dropdown-error">
        {{ modelState.error }}
      </div>
    </div>

    <!-- Click-away overlay -->
    <div v-if="isOpen" class="click-away" @click="isOpen = false"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import {
  state as modelState,
  activeLabel,
  fetchModels,
  selectModel,
  testConnection,
} from '../store/modelStore'
import { getStepOverrides, setStepOverride, clearStepOverride, estimateCost, getModelStats } from '../api/models'

const isOpen = ref(false)
const testingModel = ref(null)
const activeTab = ref('global')
const costCache = reactive({})
const modelStats = reactive({})

const stepOverrides = reactive({
  steps: ['ontology', 'graph', 'simulation', 'report', 'interaction'],
  step_overrides: {},
  global_active: {},
})

const stepLabels = {
  ontology: '01 Ontology',
  graph: '02 Graph Build',
  simulation: '03 Simulation',
  report: '04 Report',
  interaction: '05 Interaction',
}

const statusDotClass = computed(() => {
  if (!modelState.active.model_name) return 'dot-gray'
  if (modelState.testResult?.status === 'ok') return 'dot-green'
  if (modelState.testResult?.status === 'error') return 'dot-red'
  return 'dot-yellow'
})

function toggleOpen() {
  isOpen.value = !isOpen.value
  if (isOpen.value && modelState.providers.length === 0) {
    fetchModels()
  }
  // Pre-fetch cost estimates and stats for all models
  if (isOpen.value) {
    fetchAllCosts()
    fetchModelStats()
  }
}

async function fetchAllCosts() {
  for (const provider of modelState.providers) {
    for (const model of provider.models) {
      const key = `${provider.id}/${model.id}`
      if (costCache[key] !== undefined) continue
      try {
        const res = await estimateCost({ model_name: model.id, provider_id: provider.id })
        costCache[key] = res.data
      } catch { /* ignore */ }
    }
  }
}

async function fetchModelStats() {
  try {
    const res = await getModelStats()
    Object.assign(modelStats, res.data)
  } catch { /* ignore */ }
}

function formatCost(data) {
  if (!data) return ''
  if (data.is_free) return 'FREE'
  return `~$${data.total_cost_usd.toFixed(3)}`
}

async function handleSelect(provider, model) {
  const ok = await selectModel(provider.id, model.id, provider.base_url)
  if (ok) {
    handleTest()
  }
}

async function handleTest() {
  if (!modelState.active.model_name) return
  testingModel.value = `${modelState.active.provider_id}/${modelState.active.model_name}`
  await testConnection(
    modelState.active.provider_id,
    modelState.active.model_name,
    modelState.active.base_url,
  )
  testingModel.value = null
}

async function loadStepOverrides() {
  try {
    const res = await getStepOverrides()
    Object.assign(stepOverrides, res.data)
  } catch { /* ignore */ }
}

function stepSelectValue(step) {
  const override = stepOverrides.step_overrides[step]
  if (!override) return ''
  return `${override.provider_id}|${override.model_name}|${override.base_url || ''}`
}

async function handleStepChange(step, event) {
  const value = event.target.value
  if (!value) {
    // Clear override
    try {
      await clearStepOverride(step)
      stepOverrides.step_overrides[step] = null
    } catch { /* ignore */ }
  } else {
    const [provider_id, model_name, base_url] = value.split('|')
    try {
      await setStepOverride(step, { provider_id, model_name, base_url: base_url || undefined })
      stepOverrides.step_overrides[step] = { provider_id, model_name, base_url }
    } catch { /* ignore */ }
  }
}

onMounted(() => {
  if (modelState.providers.length === 0) {
    fetchModels()
  }
})
</script>

<style scoped>
.model-selector {
  position: relative;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  z-index: 1000;
}

.model-badge-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid #444;
  color: #fff;
  padding: 5px 10px;
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  transition: border-color 0.2s;
  white-space: nowrap;
}

.model-badge-btn:hover {
  border-color: #FF4500;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-green { background: #4CAF50; }
.dot-yellow { background: #FFC107; }
.dot-red { background: #F44336; }
.dot-gray { background: #666; }

.badge-label {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.badge-arrow {
  font-size: 8px;
  opacity: 0.6;
}

/* Dropdown */
.click-away {
  position: fixed;
  inset: 0;
  z-index: 999;
}

.dropdown-panel {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 360px;
  max-height: 520px;
  overflow-y: auto;
  background: #1a1a1a;
  border: 1px solid #333;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  z-index: 1001;
}

.dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #333;
}

.dropdown-title {
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #999;
}

.close-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}
.close-btn:hover { color: #fff; }

/* Tab bar */
.tab-bar {
  display: flex;
  border-bottom: 1px solid #333;
}

.tab-btn {
  flex: 1;
  padding: 8px 0;
  border: none;
  background: transparent;
  font-family: inherit;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #555;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn:hover { color: #888; }
.tab-btn.active {
  color: #FF4500;
  border-bottom-color: #FF4500;
}

.dropdown-loading {
  padding: 20px;
  text-align: center;
  color: #666;
}

/* Providers */
.provider-group {
  border-bottom: 1px solid #222;
}

.provider-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #111;
}

.provider-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.provider-name {
  font-weight: 600;
  font-size: 11px;
  color: #ccc;
}

.provider-type {
  margin-left: auto;
  font-size: 10px;
  color: #555;
  text-transform: uppercase;
}

.provider-disabled {
  padding: 6px 12px 8px 26px;
  font-size: 10px;
  color: #555;
  font-style: italic;
}

/* Models */
.model-list {
  display: flex;
  flex-direction: column;
}

.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 12px 7px 26px;
  background: transparent;
  border: none;
  color: #aaa;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
  gap: 8px;
}

.model-item:hover {
  background: #222;
  color: #fff;
}

.model-item.active {
  color: #FF4500;
  font-weight: 600;
}

.model-item.testing {
  opacity: 0.5;
}

.model-cost {
  font-size: 9px;
  color: #666;
  margin-left: auto;
  white-space: nowrap;
}

.model-item.active .model-cost { color: #FF4500; opacity: 0.7; }

.active-check {
  color: #FF4500;
  font-size: 12px;
  flex-shrink: 0;
}

.model-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Footer */
.dropdown-footer {
  padding: 10px 12px;
  border-top: 1px solid #333;
  display: flex;
  align-items: center;
  gap: 10px;
}

.test-btn {
  background: #222;
  border: 1px solid #444;
  color: #ccc;
  padding: 5px 12px;
  font-family: inherit;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.test-btn:hover:not(:disabled) {
  border-color: #FF4500;
  color: #FF4500;
}

.test-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.test-result {
  font-size: 10px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-result.ok { color: #4CAF50; }
.test-result.error { color: #F44336; }

.model-stats {
  font-size: 9px;
  color: #666;
  padding-top: 4px;
  border-top: 1px solid #333;
  margin-top: 4px;
}

.stat-label {
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  color: #777;
  margin-top: 2px;
}

.dropdown-error {
  padding: 8px 12px;
  font-size: 10px;
  color: #F44336;
  background: rgba(244, 67, 54, 0.1);
}

/* ── Per-Step Tab ── */
.step-list {
  padding: 4px 0;
}

.step-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #222;
  gap: 8px;
}

.step-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.step-name-label {
  font-size: 11px;
  font-weight: 600;
  color: #ccc;
}

.step-model {
  font-size: 9px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-actions {
  flex-shrink: 0;
}

.step-select {
  background: #222;
  border: 1px solid #444;
  color: #ccc;
  padding: 4px 6px;
  font-family: inherit;
  font-size: 10px;
  cursor: pointer;
  max-width: 160px;
  border-radius: 0;
}

.step-select:focus {
  border-color: #FF4500;
  outline: none;
}

.step-select option {
  background: #1a1a1a;
  color: #ccc;
}

.step-select optgroup {
  color: #888;
  font-weight: 600;
}
</style>
