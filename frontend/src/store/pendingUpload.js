/**
 * Temporary storage of files, URLs, search queries and requirements pending upload
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  urls: '',
  searchQuery: '',
  simulationRequirement: '',
  isPending: false
})

export function setPendingUpload(files, requirement, urls = '', searchQuery = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.urls = urls
  state.searchQuery = searchQuery
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    urls: state.urls,
    searchQuery: state.searchQuery,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.urls = ''
  state.searchQuery = ''
  state.simulationRequirement = ''
  state.isPending = false
}

export default state
