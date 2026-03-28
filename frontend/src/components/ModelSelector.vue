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

      <!-- Loading state -->
      <div v-if="modelState.loading" class="dropdown-loading">
        Loading models...
      </div>

      <!-- Provider list -->
      <div v-else class="provider-list">
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
              <span
                v-if="modelState.active.provider_id === provider.id && modelState.active.model_name === model.id"
                class="active-check"
              >&#10003;</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Test button -->
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
      </div>

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
import { ref, computed, onMounted } from 'vue'
import {
  state as modelState,
  activeLabel,
  fetchModels,
  selectModel,
  testConnection,
} from '../store/modelStore'

const isOpen = ref(false)
const testingModel = ref(null)

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
}

async function handleSelect(provider, model) {
  const ok = await selectModel(provider.id, model.id, provider.base_url)
  if (ok) {
    // auto-test after selection
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
  width: 320px;
  max-height: 480px;
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

.active-check {
  color: #FF4500;
  font-size: 12px;
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

.dropdown-error {
  padding: 8px 12px;
  font-size: 10px;
  color: #F44336;
  background: rgba(244, 67, 54, 0.1);
}
</style>
