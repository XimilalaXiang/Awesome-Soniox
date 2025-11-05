<template>
  <div class="card mb-6">
    <div class="flex items-center justify-between">
      <!-- 状态指示器 -->
      <div class="flex items-center space-x-4">
        <div class="flex items-center">
          <div
            class="w-3 h-3 rounded-full mr-2 transition-all duration-300"
            :class="{
              'bg-green-500 animate-pulse': store.isRecording,
              'bg-gray-300': !store.isRecording
            }"
          ></div>
          <span class="text-sm font-medium">
            {{ store.isRecording ? '录音中' : '未录音' }}
          </span>
        </div>

        <div v-if="store.isConnected" class="flex items-center text-green-600">
          <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
          </svg>
          <span class="text-sm">已连接</span>
        </div>

        <div v-if="recordingTime > 0" class="text-sm font-mono">
          {{ formatRecordingTime(recordingTime) }}
        </div>
      </div>

      <!-- 控制按钮 -->
      <div class="flex space-x-3">
        <button
          v-if="!store.isRecording"
          @click="startRecording"
          :disabled="!canStart"
          class="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clip-rule="evenodd"/>
          </svg>
          开始录音
        </button>

        <button
          v-if="store.isRecording"
          @click="stopRecording"
          class="btn-danger"
        >
          <svg class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd"/>
          </svg>
          停止录音
        </button>

        <button
          v-if="store.isRecording"
          @click="finalize"
          class="btn-secondary"
          title="立即完成当前转录"
        >
          <svg class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
          </svg>
          完成当前句
        </button>

        <button
          v-if="store.hasTranscript && !store.isRecording"
          @click="clearTranscript"
          class="btn-secondary"
        >
          清空
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="mt-4 p-3 bg-red-50 border-2 border-red-600 rounded-md text-red-600">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'
import { TranscriptionWebSocket } from '@/services/websocket'

const store = useTranscriptionStore()
const error = ref('')
const recordingTime = ref(0)
let recordingTimer = null
let wsClient = null

const canStart = computed(() => {
  return store.sonioxConfig.api_key && !store.isRecording
})

async function startRecording() {
  error.value = ''

  try {
    // 创建 WebSocket 客户端
    wsClient = new TranscriptionWebSocket(store.sonioxConfig, {
      onConnected: (data) => {
        store.isConnected = true
        store.sessionId = data.session_id
      },
      onTranscription: (data) => {
        handleTranscription(data)
      },
      onSessionCompleted: () => {
        store.isRecording = false
        stopTimer()
      },
      onError: (err) => {
        error.value = `错误: ${err.message || err}`
        store.isRecording = false
        store.isConnected = false
        stopTimer()
      },
      onDisconnected: () => {
        store.isConnected = false
      }
    })

    // 连接到服务器
    await wsClient.connect()

    // 开始录音
    const started = await wsClient.startRecording()

    if (started) {
      store.isRecording = true
      startTimer()
    } else {
      throw new Error('无法开始录音')
    }
  } catch (err) {
    error.value = `启动失败: ${err.message}`
    console.error(err)
  }
}

function stopRecording() {
  if (wsClient) {
    wsClient.stopRecording()
    store.isRecording = false
    stopTimer()
  }
}

function finalize() {
  if (wsClient) {
    wsClient.finalize()
  }
}

function clearTranscript() {
  if (confirm('确定要清空转录内容吗？')) {
    store.clearTranscript()
  }
}

function handleTranscription(data) {
  const tokens = data.tokens
  let currentSpeaker = null
  let currentSegmentText = ''

  for (const token of tokens) {
    const speaker = token.speaker || 'Speaker 0'

    // 如果发言人改变，创建新的 segment
    if (speaker !== currentSpeaker) {
      if (currentSpeaker !== null && currentSegmentText) {
        // 保存之前的 segment
        store.addSegment({
          speaker: currentSpeaker,
          text: currentSegmentText,
          start_time: token.start_ms,
          end_time: token.end_ms,
        })
      }

      currentSpeaker = speaker
      currentSegmentText = token.text
    } else {
      currentSegmentText += token.text
    }

    // 更新当前 segment（用于实时显示）
    if (!token.is_final) {
      store.currentSegment = {
        speaker: currentSpeaker,
        text: currentSegmentText,
      }
    }
  }

  // 如果所有 tokens 都是 final，清空当前 segment
  const allFinal = tokens.every(t => t.is_final)
  if (allFinal && currentSpeaker && currentSegmentText) {
    store.addSegment({
      speaker: currentSpeaker,
      text: currentSegmentText,
      start_time: tokens[0].start_ms,
      end_time: tokens[tokens.length - 1].end_ms,
    })
    store.currentSegment = null
  }
}

function startTimer() {
  recordingTime.value = 0
  recordingTimer = setInterval(() => {
    recordingTime.value++
  }, 1000)
}

function stopTimer() {
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }
}

function formatRecordingTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

onUnmounted(() => {
  if (wsClient) {
    wsClient.close()
  }
  stopTimer()
})
</script>
