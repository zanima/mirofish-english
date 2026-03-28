/**
 * Composable for detecting LLM errors and prompting model switch.
 *
 * Usage:
 *   const { withFallback, showSwitchDialog, dismissDialog } = useModelFallback()
 *
 *   try {
 *     await withFallback(() => someApiCall())
 *   } catch (err) {
 *     // error already shown to user via dialog if it was an LLM error
 *   }
 */
import { ref } from 'vue'

const LLM_ERROR_PATTERNS = [
  /timeout/i,
  /EOF/,
  /rate.?limit/i,
  /429/,
  /token.*exhaust/i,
  /quota.*exceeded/i,
  /empty content/i,
  /connection.*refused/i,
  /ECONNREFUSED/,
  /503/,
  /502/,
  /model.*not.*found/i,
]

function isLLMError(err) {
  const msg = err?.message || String(err)
  return LLM_ERROR_PATTERNS.some(p => p.test(msg))
}

export function useModelFallback() {
  const showSwitchDialog = ref(false)
  const lastError = ref(null)
  const retryFn = ref(null)

  async function withFallback(apiCall, onRetry) {
    try {
      return await apiCall()
    } catch (err) {
      if (isLLMError(err)) {
        lastError.value = err?.message || String(err)
        retryFn.value = onRetry || null
        showSwitchDialog.value = true
      }
      throw err
    }
  }

  function dismissDialog() {
    showSwitchDialog.value = false
    lastError.value = null
    retryFn.value = null
  }

  async function retryAfterSwitch() {
    showSwitchDialog.value = false
    if (retryFn.value) {
      const fn = retryFn.value
      retryFn.value = null
      lastError.value = null
      return await fn()
    }
  }

  return {
    showSwitchDialog,
    lastError,
    withFallback,
    dismissDialog,
    retryAfterSwitch,
  }
}
