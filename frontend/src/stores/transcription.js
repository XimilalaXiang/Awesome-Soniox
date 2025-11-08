import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTranscriptionStore = defineStore('transcription', () => {
  // 状态
  const isRecording = ref(false)
  const isConnected = ref(false)
  const sessionId = ref(null)
  const segments = ref([])
  const currentSegment = ref(null)
  const fullTranscript = ref('')

  // WebSocket 连接
  const ws = ref(null)

  // Soniox 配置
  const sonioxConfig = ref({
    api_key: localStorage.getItem('soniox_api_key') || '',
    model: 'stt-rt-v3',
    enable_speaker_diarization: true,
    enable_language_identification: false,
    enable_endpoint_detection: true,
    language_hints: []
  })

  // OpenAI 配置
  const openaiConfig = ref({
    api_url: localStorage.getItem('openai_api_url') || 'https://api.openai.com/v1',
    api_key: localStorage.getItem('openai_api_key') || '',
    model: localStorage.getItem('openai_model') || 'gpt-4o-mini'
  })

  // 计算属性
  const hasTranscript = computed(() => segments.value.length > 0)

  const speakerCount = computed(() => {
    const speakers = new Set(segments.value.map(s => s.speaker))
    return speakers.size
  })

  // 方法
  function saveSonioxConfig(config) {
    const normalized = {
      ...config,
      api_key: (config.api_key || '').trim().replace(/\s+/g, '')
    }
    sonioxConfig.value = normalized
    localStorage.setItem('soniox_api_key', normalized.api_key)
  }

  function saveOpenAIConfig(config) {
    openaiConfig.value = { ...config }
    localStorage.setItem('openai_api_url', config.api_url)
    localStorage.setItem('openai_api_key', config.api_key)
    localStorage.setItem('openai_model', config.model)
  }

  function addSegment(segment) {
    segments.value.push(segment)
  }

  function updateCurrentSegment(text) {
    if (currentSegment.value) {
      currentSegment.value.text = text
    }
  }

  function clearTranscript() {
    segments.value = []
    currentSegment.value = null
    fullTranscript.value = ''
  }

  function reset() {
    isRecording.value = false
    isConnected.value = false
    sessionId.value = null
    clearTranscript()
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  return {
    // 状态
    isRecording,
    isConnected,
    sessionId,
    segments,
    currentSegment,
    fullTranscript,
    ws,
    sonioxConfig,
    openaiConfig,

    // 计算属性
    hasTranscript,
    speakerCount,

    // 方法
    saveSonioxConfig,
    saveOpenAIConfig,
    addSegment,
    updateCurrentSegment,
    clearTranscript,
    reset
  }
})
