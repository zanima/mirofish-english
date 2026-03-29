<template>
  <div class="home-container">
    <!-- Top navigation bar -->
    <nav class="navbar">
      <div class="nav-left">
        <div class="nav-brand">MIROFISH</div>
        <span class="nav-version">v0.1-preview</span>
      </div>
      <div class="nav-center">
        <ModelSelector />
      </div>
      <div class="nav-right">
        <a href="https://github.com/666ghj/MiroFish" target="_blank" class="github-link">
          GitHub <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- Hero + action console side-by-side -->
      <section class="hero-action-row">
        <!-- Left: hero -->
        <div class="hero-col">
          <div class="tag-row">
            <span class="orange-tag">Universal Swarm Intelligence Engine</span>
          </div>

          <h1 class="main-title">
            Upload Any Report,<br>
            <span class="gradient-text">Simulate the Future</span>
          </h1>

          <p class="hero-desc">
            From a single paragraph, <strong>MiroFish</strong> extracts real-world seeds,
            generates a parallel world of <span class="highlight-orange">intelligent Agents</span>,
            and lets you rehearse the future in a digital sandbox.
          </p>

          <!-- Workflow steps — horizontal pills -->
          <div class="workflow-pills">
            <div class="pill" v-for="(step, i) in steps" :key="i">
              <span class="pill-num">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="pill-label">{{ step }}</span>
            </div>
          </div>

          <!-- Logo accent -->
          <div class="logo-accent">
            <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="MiroFish" class="accent-logo" />
          </div>
        </div>

        <!-- Right: action console -->
        <div class="action-col">
          <div class="console-box">
            <!-- Source tabs -->
            <div class="source-tabs">
              <button
                v-for="tab in sourceTabs"
                :key="tab.id"
                class="source-tab"
                :class="{ active: activeSource === tab.id }"
                @click="activeSource = tab.id"
              >
                <span class="tab-icon">{{ tab.icon }}</span>
                {{ tab.label }}
              </button>
            </div>

            <!-- Source: Files -->
            <div v-if="activeSource === 'files'" class="console-section">
              <div class="console-header">
                <span class="console-label">Upload Files</span>
                <span class="console-meta">PDF, MD, TXT, CSV</span>
              </div>
              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt,.csv"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">Drag & drop files here</div>
                  <div class="upload-hint">or click to browse</div>
                </div>
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">&#9634;</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">&times;</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Source: URL -->
            <div v-else-if="activeSource === 'url'" class="console-section">
              <div class="console-header">
                <span class="console-label">Paste URLs</span>
                <span class="console-meta">one per line</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="urlsInput"
                  class="code-input url-input"
                  placeholder="https://en.wikipedia.org/wiki/...&#10;https://arxiv.org/abs/...&#10;https://news.example.com/article"
                  rows="4"
                  :disabled="loading"
                ></textarea>
              </div>
              <div class="source-hint">Pages will be fetched and text extracted automatically</div>
            </div>

            <!-- Source: Search -->
            <div v-else-if="activeSource === 'search'" class="console-section">
              <div class="console-header">
                <span class="console-label">Search the Web</span>
                <span class="console-meta">top 5 results</span>
              </div>
              <div class="input-wrapper">
                <input
                  v-model="searchQuery"
                  class="search-input"
                  type="text"
                  placeholder="e.g. Tesla stock prediction 2026 analysis"
                  :disabled="loading"
                  @keydown.enter.prevent
                />
              </div>
              <div class="source-hint">Searches DuckDuckGo and extracts text from top results</div>
            </div>

            <!-- Divider -->
            <div class="console-divider"><span>Prompt</span></div>

            <!-- Prompt area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ Simulation Prompt</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// What public opinion trends would emerge if..."
                  rows="4"
                  :disabled="loading"
                ></textarea>
              </div>
            </div>

            <!-- Launch button -->
            <div class="console-section btn-section">
              <button
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">Launch Engine</span>
                <span v-else>Initializing...</span>
                <span class="btn-arrow">&rarr;</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Historical project database -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import ModelSelector from '../components/ModelSelector.vue'
import { setPendingUpload } from '../store/pendingUpload'

const router = useRouter()

const steps = ['Graph Build', 'Env Setup', 'Simulation', 'Report', 'Interact']

const formData = ref({ simulationRequirement: '' })
const files = ref([])
const loading = ref(false)
const isDragOver = ref(false)
const fileInput = ref(null)

// Source tabs for seed data input
const activeSource = ref('files')
const sourceTabs = [
  { id: 'files', icon: '↑', label: 'Files' },
  { id: 'url', icon: '🔗', label: 'URL' },
  { id: 'search', icon: '🔍', label: 'Search' }
]
const urlsInput = ref('')
const searchQuery = ref('')

const canSubmit = computed(() => {
  const hasPrompt = formData.value.simulationRequirement.trim() !== ''
  const hasFiles = files.value.length > 0
  const hasUrls = urlsInput.value.trim() !== ''
  const hasSearch = searchQuery.value.trim() !== ''
  return hasPrompt && (hasFiles || hasUrls || hasSearch)
})

const triggerFileInput = () => { if (!loading.value) fileInput.value?.click() }

const handleFileSelect = (event) => addFiles(Array.from(event.target.files))
const handleDragOver = () => { if (!loading.value) isDragOver.value = true }
const handleDragLeave = () => { isDragOver.value = false }
const handleDrop = (e) => {
  isDragOver.value = false
  if (!loading.value) addFiles(Array.from(e.dataTransfer.files))
}

const addFiles = (newFiles) => {
  files.value.push(...newFiles.filter(f => ['pdf', 'md', 'txt', 'csv'].includes(f.name.split('.').pop().toLowerCase())))
}
const removeFile = (index) => { files.value.splice(index, 1) }

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  setPendingUpload(files.value, formData.value.simulationRequirement, urlsInput.value, searchQuery.value)
  router.push({ name: 'Process', params: { projectId: 'new' } })
}
</script>

<style scoped>
/* ── Dark-first theme with system-aware override ──────────── */
.home-container {
  --bg: #0d0d0d;
  --bg-surface: #161616;
  --bg-elevated: #1c1c1c;
  --fg: #e8e8e8;
  --fg-muted: #888;
  --fg-dim: #555;
  --orange: #FF4500;
  --border: #2a2a2a;
  --border-hover: #444;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;

  min-height: 100vh;
  background: var(--bg);
  font-family: var(--font-sans);
  color: var(--fg);
}

/* Light mode override (follows system) */
@media (prefers-color-scheme: light) {
  .home-container {
    --bg: #ffffff;
    --bg-surface: #f7f7f7;
    --bg-elevated: #ffffff;
    --fg: #111111;
    --fg-muted: #666666;
    --fg-dim: #aaaaaa;
    --border: #e0e0e0;
    --border-hover: #999;
  }
}

/* ── Navbar ───────────────────────────────────────────────── */
.navbar {
  height: 50px;
  background: #000;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 28px;
  border-bottom: 1px solid #1a1a1a;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1.5px;
  font-size: 1rem;
}

.nav-version {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: #444;
}

.nav-center { display: flex; align-items: center; }
.nav-right { display: flex; align-items: center; }

.github-link {
  color: #fff;
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 500;
  opacity: 0.5;
  transition: opacity 0.2s;
}
.github-link:hover { opacity: 1; }
.arrow { font-family: sans-serif; }

/* ── Main content ─────────────────────────────────────────── */
.main-content {
  max-width: 1280px;
  margin: 0 auto;
  padding: 44px 32px 32px;
}

/* ── Hero + Action row ────────────────────────────────────── */
.hero-action-row {
  display: flex;
  gap: 52px;
  align-items: flex-start;
  margin-bottom: 52px;
}

.hero-col {
  flex: 1;
  min-width: 0;
  padding-top: 4px;
}

.tag-row { margin-bottom: 16px; }

.orange-tag {
  background: var(--orange);
  color: #fff;
  padding: 3px 10px;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.5px;
  font-size: 0.65rem;
  text-transform: uppercase;
}

.main-title {
  font-size: 3rem;
  line-height: 1.12;
  font-weight: 500;
  margin: 0 0 20px 0;
  letter-spacing: -1.5px;
  color: var(--fg);
}

.gradient-text {
  background: linear-gradient(90deg, var(--fg) 0%, var(--fg-muted) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--fg-muted);
  margin-bottom: 28px;
  max-width: 500px;
}

.hero-desc strong {
  color: var(--fg);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: 0.88em;
}

/* Workflow pills */
.workflow-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 32px;
}

.pill {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border);
  padding: 5px 11px;
  font-size: 0.75rem;
  transition: border-color 0.2s;
}
.pill:hover { border-color: var(--border-hover); }

.pill-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--orange);
  font-size: 0.68rem;
}

.pill-label {
  font-weight: 500;
  color: var(--fg-muted);
}

/* Logo accent */
.logo-accent {
  margin-top: 4px;
}

.accent-logo {
  height: 52px;
  opacity: 0.35;
  transition: opacity 0.3s;
  filter: grayscale(0.3);
}
.accent-logo:hover { opacity: 0.7; }

/* ── Action console ───────────────────────────────────────── */
.action-col {
  flex: 1;
  min-width: 370px;
  max-width: 500px;
}

.console-box {
  border: 1px solid var(--border);
  padding: 5px;
  background: var(--bg-surface);
}

.console-section {
  padding: 14px 16px;
}
.console-section.btn-section { padding-top: 0; }

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 9px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--fg-dim);
}

/* Source tabs */
.source-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
}

.source-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 0;
  border: none;
  background: transparent;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--fg-dim);
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
  border-bottom: 2px solid transparent;
}

.source-tab:hover { color: var(--fg-muted); }

.source-tab.active {
  color: var(--orange);
  border-bottom-color: var(--orange);
}

.tab-icon { font-size: 0.82rem; }

.source-hint {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--fg-dim);
  margin-top: 7px;
  padding: 0 2px;
}

.url-input {
  min-height: 90px;
}

.search-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 12px 14px;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  line-height: 1.6;
  outline: none;
  color: var(--fg);
}

.search-input::placeholder {
  color: var(--fg-dim);
}

/* Upload zone */
.upload-zone {
  border: 1px dashed var(--border);
  height: 120px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.25s;
  background: var(--bg-elevated);
}
.upload-zone.has-files { align-items: flex-start; }
.upload-zone:hover,
.upload-zone.drag-over {
  background: var(--bg);
  border-color: var(--orange);
}

.upload-placeholder { text-align: center; }

.upload-icon {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
  color: var(--fg-dim);
  font-size: 0.85rem;
}

.upload-title {
  font-weight: 500;
  font-size: 0.82rem;
  margin-bottom: 2px;
  color: var(--fg);
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--fg-dim);
}

.file-list {
  width: 100%;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--bg);
  padding: 5px 9px;
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--fg);
}

.file-icon { color: var(--fg-dim); font-size: 0.8rem; }

.file-name {
  flex: 1;
  margin: 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--fg-dim);
  padding: 0 2px;
}
.remove-btn:hover { color: var(--orange); }

/* Divider */
.console-divider {
  display: flex;
  align-items: center;
  margin: 3px 0;
}
.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}
.console-divider span {
  padding: 0 10px;
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--fg-dim);
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* Prompt input */
.input-wrapper {
  border: 1px solid var(--border);
  background: var(--bg-elevated);
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 12px 14px;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 90px;
  color: var(--fg);
}

.code-input::placeholder {
  color: var(--fg-dim);
}

/* Launch button */
.start-engine-btn {
  width: 100%;
  background: var(--orange);
  color: #fff;
  border: 1px solid var(--orange);
  padding: 15px 18px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.95rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.25s ease;
  letter-spacing: 1px;
  overflow: hidden;
}

.start-engine-btn:not(:disabled) {
  animation: pulse-glow 2.5s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: #e63e00;
  border-color: #e63e00;
  transform: translateY(-1px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: var(--bg-elevated);
  color: var(--fg-dim);
  cursor: not-allowed;
  border-color: var(--border);
}

@keyframes pulse-glow {
  0% { box-shadow: 0 0 0 0 rgba(255, 69, 0, 0.3); }
  70% { box-shadow: 0 0 0 8px rgba(255, 69, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 69, 0, 0); }
}

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 900px) {
  .hero-action-row { flex-direction: column; }
  .action-col { min-width: 100%; max-width: 100%; }
  .main-title { font-size: 2.2rem; }
}
</style>
