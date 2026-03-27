import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

// Create axios instance
const service = axios.create({
  // Default to same-origin so remote browsers use the host that served the UI.
  // In local dev, Vite proxies /api to the backend. An explicit VITE_API_BASE_URL
  // can still override this when a separate API host is required.
  baseURL: apiBaseUrl,
  timeout: 300000, // 5 minute timeout (entity generation may take longer)
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
service.interceptors.request.use(
  config => {
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (fault tolerance retry mechanism)
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // If the returned status code is not success, throw an error
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    console.error('Response error:', error)
    const backendError = error.response?.data?.error || error.response?.data?.message
    
    // Handle timeout
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
      return Promise.reject(new Error(backendError || 'Request timeout'))
    }
    
    // Handle network error
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
      return Promise.reject(new Error(backendError || 'Network error - please check your connection'))
    }
    
    return Promise.reject(new Error(backendError || error.message || 'Request failed'))
  }
)

// Request function with retry
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      
      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
