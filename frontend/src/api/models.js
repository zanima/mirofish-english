/**
 * Model management API
 */
import service from './index'

export const getAvailableModels = () => service.get('/api/models/available')

export const getActiveModel = () => service.get('/api/models/active')

export const setActiveModel = (data) => service.post('/api/models/active', data)

export const testModel = (data) => service.post('/api/models/test', data)

// Per-step model selection
export const getStepOverrides = () => service.get('/api/models/steps')

export const setStepOverride = (step, data) => service.post(`/api/models/steps/${step}`, data)

export const clearStepOverride = (step) => service.delete(`/api/models/steps/${step}`)

// Cost estimation
export const estimateCost = (data) => service.post('/api/models/estimate', data)
