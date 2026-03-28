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
      <!-- Compact hero + action console side-by-side -->
      <section class="hero-action-row">
        <!-- Left: compact hero -->
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

          <!-- Compact workflow steps — horizontal pills -->
          <div class="workflow-pills">
            <div class="pill" v-for="(step, i) in steps" :key="i">
              <span class="pill-num">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="pill-label">{{ step }}</span>
            </div>
          </div>
        </div>

        <!-- Right: action console (upload + prompt + launch) -->
        <div class="action-col">
          <div class="console-box">
            <!-- Upload area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / Seed Data</span>
                <span class="console-meta">PDF, MD, TXT</span>
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
                  accept=".pdf,.md,.txt"
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

            <!-- Divider -->
            <div class="console-divider"><span>Prompt</span></div>

            <!-- Prompt area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / Simulation Prompt</span>
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

      <!-- Logo strip -->
      <div class="logo-strip">
        <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="MiroFish Logo" class="strip-logo" />
        <div class="strip-stats">
          <div class="stat-box">
            <div class="stat-val">Low Cost</div>
            <div class="stat-lbl">~$5 avg / sim</div>
          </div>
          <div class="stat-box">
            <div class="stat-val">Scalable</div>
            <div class="stat-lbl">Millions of Agents</div>
          </div>
        </div>
      </div>

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

const router = useRouter()

const steps = ['Graph Build', 'Env Setup', 'Simulation', 'Report', 'Interact']

// Form data
const formData = ref({
  simulationRequirement: ''
})

// File list
const files = ref([])

// Status
const loading = ref(false)
const isDragOver = ref(false)

// File input reference
const fileInput = ref(null)

// Computed property: whether can submit
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// Trigger file selection
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// Handle file selection
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// Handle drag-and-drop
const handleDragOver = () => {
  if (!loading.value) isDragOver.value = true
}
const handleDragLeave = () => {
  isDragOver.value = false
}
const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  addFiles(Array.from(e.dataTransfer.files))
}

// Add files
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// Remove file
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// Start simulation
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    router.push({ name: 'Process', params: { projectId: 'new' } })
  })
}
</script>

<style scoped>
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-text: #666666;
  --border: #E5E5E5;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* ── Navbar ───────────────────────────────────────────────── */
.navbar {
  height: 54px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.1rem;
}

.nav-version {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #666;
}

.nav-center {
  display: flex;
  align-items: center;
}

.nav-right {
  display: flex;
  align-items: center;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 500;
  opacity: 0.7;
  transition: opacity 0.2s;
}
.github-link:hover { opacity: 1; }
.arrow { font-family: sans-serif; }

/* ── Main content ─────────────────────────────────────────── */
.main-content {
  max-width: 1320px;
  margin: 0 auto;
  padding: 48px 36px 36px;
}

/* ── Hero + Action row ────────────────────────────────────── */
.hero-action-row {
  display: flex;
  gap: 48px;
  align-items: flex-start;
  margin-bottom: 48px;
}

/* Left: hero text */
.hero-col {
  flex: 1;
  min-width: 0;
  padding-top: 8px;
}

.tag-row {
  margin-bottom: 18px;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 3px 10px;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.5px;
  font-size: 0.7rem;
  text-transform: uppercase;
}

.main-title {
  font-size: 3.2rem;
  line-height: 1.15;
  font-weight: 500;
  margin: 0 0 22px 0;
  letter-spacing: -1.5px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000 0%, #555 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 0.95rem;
  line-height: 1.7;
  color: var(--gray-text);
  margin-bottom: 28px;
  max-width: 520px;
}

.hero-desc strong {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: 0.9em;
}

/* Workflow pills — compact horizontal steps */
.workflow-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pill {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border);
  padding: 6px 12px;
  font-size: 0.78rem;
  transition: border-color 0.2s;
}

.pill:hover {
  border-color: #999;
}

.pill-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--orange);
  font-size: 0.7rem;
}

.pill-label {
  font-weight: 500;
  color: #444;
}

/* Right: action console */
.action-col {
  flex: 1;
  min-width: 380px;
  max-width: 520px;
}

.console-box {
  border: 1px solid #CCC;
  padding: 6px;
  background: var(--white);
}

.console-section {
  padding: 16px 18px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #777;
}

/* Upload zone */
.upload-zone {
  border: 1px dashed #CCC;
  height: 130px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.25s;
  background: #FAFAFA;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover,
.upload-zone.drag-over {
  background: #F0F0F0;
  border-color: var(--orange);
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 32px;
  height: 32px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 10px;
  color: #999;
  font-size: 0.9rem;
}

.upload-title {
  font-weight: 500;
  font-size: 0.85rem;
  margin-bottom: 3px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 6px 10px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.file-icon {
  color: #999;
  font-size: 0.85rem;
}

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
  font-size: 1.1rem;
  color: #999;
  padding: 0 2px;
}
.remove-btn:hover { color: var(--orange); }

/* Divider */
.console-divider {
  display: flex;
  align-items: center;
  margin: 4px 0;
}
.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}
.console-divider span {
  padding: 0 12px;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: #BBB;
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* Prompt input */
.input-wrapper {
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 100px;
}

/* Launch button */
.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: 1px solid var(--black);
  padding: 16px 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.25s ease;
  letter-spacing: 1px;
  overflow: hidden;
}

.start-engine-btn:not(:disabled) {
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  transform: translateY(-1px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  border-color: #E5E5E5;
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.15); }
  70% { box-shadow: 0 0 0 5px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* ── Logo strip ───────────────────────────────────────────── */
.logo-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 24px 0;
  margin-bottom: 48px;
}

.strip-logo {
  height: 64px;
  opacity: 0.7;
  transition: opacity 0.3s;
}
.strip-logo:hover { opacity: 1; }

.strip-stats {
  display: flex;
  gap: 32px;
}

.stat-box {
  text-align: right;
}

.stat-val {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 600;
}

.stat-lbl {
  font-size: 0.75rem;
  color: #999;
  margin-top: 2px;
}

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 900px) {
  .hero-action-row {
    flex-direction: column;
  }
  .action-col {
    min-width: 100%;
    max-width: 100%;
  }
  .main-title {
    font-size: 2.4rem;
  }
  .logo-strip {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
  .strip-stats {
    width: 100%;
    justify-content: space-between;
  }
  .stat-box { text-align: left; }
}
</style>
