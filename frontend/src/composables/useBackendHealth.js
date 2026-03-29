/**
 * Backend health monitoring composable
 * Detects when backend is offline and provides reconnection indicators
 */
import { reactive, computed, onMounted, onUnmounted } from 'vue'

const healthState = reactive({
  online: true,
  failureCount: 0,
  reconnectCountdown: 0,
  lastCheckTime: null,
})

let healthCheckInterval = null
let countdownInterval = null

const MAX_CONSECUTIVE_FAILURES = 3
const HEALTH_CHECK_INTERVAL_MS = 5000  // Check every 5 seconds when online
const OFFLINE_CHECK_INTERVAL_MS = 2000  // Check every 2 seconds when offline

/**
 * Perform a health check by calling /health endpoint
 */
async function performHealthCheck() {
  try {
    const response = await fetch('/health', {
      method: 'GET',
      timeout: 5000
    })
    const isHealthy = response.ok

    if (isHealthy) {
      // Backend is back online
      if (!healthState.online) {
        console.log('[Backend Health] Backend is back online')
        healthState.online = true
        healthState.failureCount = 0
        healthState.reconnectCountdown = 0
      }
    } else {
      recordFailure()
    }
  } catch (error) {
    recordFailure()
  }

  healthState.lastCheckTime = new Date()
}

function recordFailure() {
  healthState.failureCount += 1

  if (healthState.failureCount >= MAX_CONSECUTIVE_FAILURES && healthState.online) {
    healthState.online = false
    console.warn(`[Backend Health] Backend appears to be offline (${healthState.failureCount} failures)`)
    startCountdown()
  }
}

function startCountdown() {
  let countdown = 10
  healthState.reconnectCountdown = countdown

  if (countdownInterval) clearInterval(countdownInterval)
  countdownInterval = setInterval(() => {
    countdown -= 1
    healthState.reconnectCountdown = countdown

    if (countdown <= 0) {
      clearInterval(countdownInterval)
      countdownInterval = null
      healthState.reconnectCountdown = 0
    }
  }, 1000)
}

/**
 * Start health monitoring
 */
function startMonitoring() {
  if (healthCheckInterval) return

  // Perform initial check
  performHealthCheck()

  // Set up periodic health checks
  healthCheckInterval = setInterval(() => {
    const interval = healthState.online ? HEALTH_CHECK_INTERVAL_MS : OFFLINE_CHECK_INTERVAL_MS

    // Adjust interval based on online status
    if (healthState.online) {
      // When online, check less frequently
      if (healthCheckInterval) clearInterval(healthCheckInterval)
      healthCheckInterval = setInterval(performHealthCheck, interval)
    }
  }, HEALTH_CHECK_INTERVAL_MS)
}

/**
 * Stop health monitoring
 */
function stopMonitoring() {
  if (healthCheckInterval) {
    clearInterval(healthCheckInterval)
    healthCheckInterval = null
  }
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
}

/**
 * Reset health state
 */
function resetHealth() {
  healthState.online = true
  healthState.failureCount = 0
  healthState.reconnectCountdown = 0
}

/**
 * Composable hook for using backend health in components
 */
export function useBackendHealth() {
  const isOnline = computed(() => healthState.online)
  const consecutiveFailures = computed(() => healthState.failureCount)
  const shouldShowReconnecting = computed(() => !healthState.online)
  const reconnectCountdown = computed(() => healthState.reconnectCountdown)

  onMounted(() => {
    startMonitoring()
  })

  onUnmounted(() => {
    stopMonitoring()
  })

  return {
    isOnline,
    consecutiveFailures,
    shouldShowReconnecting,
    reconnectCountdown,
    resetHealth,
  }
}

// Export singleton health state for global access
export { healthState }
