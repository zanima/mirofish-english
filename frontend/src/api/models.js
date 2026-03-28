/**
 * Model management API
 */
import service from './index'

export const getAvailableModels = () => service.get('/api/models/available')

export const getActiveModel = () => service.get('/api/models/active')

export const setActiveModel = (data) => service.post('/api/models/active', data)

export const testModel = (data) => service.post('/api/models/test', data)
