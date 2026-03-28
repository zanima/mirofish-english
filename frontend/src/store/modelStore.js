/**
 * Model selection store — reactive state with localStorage persistence
 */
import { reactive, computed } from 'vue'
import { getAvailableModels, setActiveModel, testModel } from '../api/models'

const STORAGE_KEY = 'mirofish_active_model'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveToStorage(selection) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selection))
  } catch { /* ignore */ }
}

const state = reactive({
  providers: [],
  active: loadFromStorage() || {
    provider_id: '',
    model_name: '',
    base_url: '',
  },
  loading: false,
  testing: false,
  testResult: null,
  error: null,
})

const activeLabel = computed(() => {
  if (!state.active.model_name) return 'No model selected'
  const provider = state.providers.find(p => p.id === state.active.provider_id)
  const providerName = provider ? provider.name : state.active.provider_id
  return `${providerName} / ${state.active.model_name}`
})

const activeProvider = computed(() => {
  return state.providers.find(p => p.id === state.active.provider_id) || null
})

async function fetchModels() {
  state.loading = true
  state.error = null
  try {
    const res = await getAvailableModels()
    state.providers = res.data.providers
    // If we have no stored selection, use what the backend reports as active
    if (!state.active.model_name && res.data.active) {
      state.active = {
        provider_id: res.data.active.provider_id,
        model_name: res.data.active.model_name,
        base_url: res.data.active.base_url,
      }
      saveToStorage(state.active)
    }
  } catch (err) {
    state.error = err.message || 'Failed to fetch models'
  } finally {
    state.loading = false
  }
}

async function selectModel(providerId, modelName, baseUrl) {
  state.error = null
  try {
    const res = await setActiveModel({
      provider_id: providerId,
      model_name: modelName,
      base_url: baseUrl || undefined,
    })
    state.active = {
      provider_id: res.data.provider_id,
      model_name: res.data.model_name,
      base_url: res.data.base_url,
    }
    saveToStorage(state.active)
    state.testResult = null
    return true
  } catch (err) {
    state.error = err.message || 'Failed to set model'
    return false
  }
}

async function testConnection(providerId, modelName, baseUrl) {
  state.testing = true
  state.testResult = null
  try {
    const res = await testModel({
      provider_id: providerId,
      model_name: modelName,
      base_url: baseUrl || undefined,
    })
    state.testResult = res.data
    return res.data
  } catch (err) {
    state.testResult = { status: 'error', error: err.message }
    return state.testResult
  } finally {
    state.testing = false
  }
}

export {
  state,
  activeLabel,
  activeProvider,
  fetchModels,
  selectModel,
  testConnection,
}

export default state
