<template>
  <div class="card">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-2xl font-bold">实时转录</h2>
      <div class="text-sm text-gray-600">
        <span v-if="store.sessionId">会话 ID: {{ store.sessionId.substring(0, 8) }}...</span>
        <span v-if="store.speakerCount > 0" class="ml-4">
          {{ store.speakerCount }} 位发言人
        </span>
      </div>
    </div>

    <!-- 转录内容 -->
    <div
      ref="transcriptContainer"
      class="transcript-container min-h-[400px] max-h-[600px] overflow-y-auto border-2 border-black rounded-lg p-4"
    >
      <div v-if="!store.hasTranscript && !currentText" class="text-center text-gray-400 py-12">
        等待开始录音...
      </div>

        <!-- 已完成的片段 -->
        <div
          v-for="(segment, index) in store.segments"
          :key="index"
          class="transcript-segment fade-in"
          :style="{ borderLeftColor: getSpeakerColor(segment.speaker) }"
        >
          <div class="speaker-label" :style="{ color: getSpeakerColor(segment.speaker) }">
            {{ segment.speaker }}
          </div>
          <div class="transcript-text">{{ segment.text }}</div>
          <div class="text-xs text-gray-400 mt-1">
            {{ formatTime(segment.start_time) }} - {{ formatTime(segment.end_time) }}
          </div>
        </div>

      <!-- 当前正在识别的片段（即使没有历史片段也要显示） -->
        <div v-if="currentText" class="transcript-segment border-dashed opacity-70">
          <div class="speaker-label">{{ currentSpeaker || 'Speaker 0' }}</div>
          <div class="transcript-text">
            {{ currentText }}
            <span class="loading-dots ml-2">
              <span></span>
              <span class="animation-delay-100"></span>
              <span class="animation-delay-200"></span>
            </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'

const store = useTranscriptionStore()
const transcriptContainer = ref(null)
const currentText = ref('')
const currentSpeaker = ref('')

// 发言人颜色映射
const speakerColors = [
  '#000000', '#333333', '#666666', '#999999',
  '#1a1a1a', '#4d4d4d', '#737373', '#a6a6a6'
]

function getSpeakerColor(speaker) {
  const speakerNum = parseInt(speaker.replace(/\D/g, '')) || 0
  return speakerColors[speakerNum % speakerColors.length]
}

function formatTime(ms) {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

// 自动滚动到底部
watch(() => store.segments.length, async () => {
  await nextTick()
  if (transcriptContainer.value) {
    transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight
  }
})

// 监听当前文本变化
watch(() => store.currentSegment, (newSegment) => {
  if (newSegment) {
    currentText.value = newSegment.text
    currentSpeaker.value = newSegment.speaker
  } else {
    currentText.value = ''
    currentSpeaker.value = ''
  }
}, { deep: true })
</script>

<style scoped>
.animation-delay-100 {
  animation-delay: 0.1s;
}

.animation-delay-200 {
  animation-delay: 0.2s;
}
</style>
