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
            {{ store.isRecording ? (isPaused ? '已暂停' : '录音中') : '未录音' }}
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
          @click="togglePause"
          class="btn-secondary"
          :title="isPaused ? '继续录音' : '暂停录音'"
        >
          <svg v-if="!isPaused" class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M6 4a1 1 0 00-1 1v10a1 1 0 102 0V5a1 1 0 00-1-1zm7 0a1 1 0 00-1 1v10a1 1 0 102 0V5a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <svg v-else class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 10l12-6v12L4 10zm3 0l7 3.5V6.5L7 10z" clip-rule="evenodd"/>
          </svg>
          {{ isPaused ? '继续录音' : '暂停录音' }}
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
const isPaused = ref(false)
// 维护每个说话人的最终文本缓冲，避免被非最终结果覆盖
const finalBySpeaker = new Map()
// 记录当前话段的起止时间（按 speaker）
const utterStartMs = new Map()
const utterEndMs = new Map()
// 跨帧保存的非最终预览文本（按 speaker），用于在说话人切换时也能落段
const previewBySpeaker = new Map()
// 当前活跃说话人（用于检测说话人切换）
let activeSpeaker = null

// 合并显示文本：移除 finalText 与 preview 之间可能的重叠，避免重复
function mergeWithOverlap(finalText, preview) {
  const a = finalText || ''
  const b = preview || ''
  if (!a || !b) return a + b
  const maxCheck = Math.min(a.length, 80) // 限制重叠检查窗口
  // 从可能的最大重叠开始向前查找
  for (let n = maxCheck; n > 0; n--) {
    const suffix = a.slice(-n)
    if (b.startsWith(suffix)) {
      return a + b.slice(n)
    }
  }
  return a + b
}

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
      isPaused.value = false
      startTimer()
    } else {
      // 优先使用底层回调已写入的错误信息
      const fallback = '无法开始录音'
      const msg = (error.value && typeof error.value === 'string')
        ? error.value.replace(/^错误:\s*/, '')
        : fallback
      throw new Error(msg || fallback)
    }
  } catch (err) {
    const msg = (err && err.message) ? err.message : String(err || '未知错误')
    error.value = `启动失败: ${msg}`
    console.error(err)
  }
}

function stopRecording() {
  if (wsClient) {
    wsClient.stopRecording()
    store.isRecording = false
    isPaused.value = false
    stopTimer()
  }
}

async function togglePause() {
  if (!wsClient) return
  try {
    if (!isPaused.value) {
      wsClient.pause()
      isPaused.value = true
    } else {
      const resumed = await wsClient.resume()
      if (resumed) {
        isPaused.value = false
      }
    }
  } catch (e) {
    console.error(e)
  }
}

function clearTranscript() {
  if (confirm('确定要清空转录内容吗？')) {
    store.clearTranscript()
  }
}

function handleTranscription(data) {
  const tokens = data.tokens
  // 本次帧的临时预览文本（按 speaker）
  const nonFinalPreview = new Map()
  let lastSpeakerInFrame = null

  // 将指定说话人的缓冲落为一个段落
  function commitSpeakerSegment(speaker) {
    if (!speaker) return
    const finalText = (finalBySpeaker.get(speaker) || '').replace(/<(end|fin)>/g, '')
    const text = finalText
    if (text) {
      store.addSegment({
        speaker,
        text,
        start_time: utterStartMs.get(speaker) ?? 0,
        end_time: utterEndMs.get(speaker) ?? 0,
      })
    }
    // 清理该说话人的缓冲
    finalBySpeaker.set(speaker, '')
    previewBySpeaker.set(speaker, '')
    utterStartMs.delete(speaker)
    utterEndMs.delete(speaker)
  }

  for (const token of tokens) {
    const speaker = token.speaker || 'Speaker 0'
    lastSpeakerInFrame = speaker

    // 说话人切换：先将上一个活跃说话人的内容（final+preview）落段，确保历史可见
    if (activeSpeaker && speaker !== activeSpeaker) {
      commitSpeakerSegment(activeSpeaker)
    }
    if (!activeSpeaker) activeSpeaker = speaker
    if (speaker !== activeSpeaker) activeSpeaker = speaker

    if (token.is_final) {
      // 记录起始时间
      if (!utterStartMs.has(speaker)) utterStartMs.set(speaker, token.start_ms)
      // 追加到最终缓冲
      const prev = finalBySpeaker.get(speaker) || ''
      finalBySpeaker.set(speaker, prev + (token.text || ''))
      utterEndMs.set(speaker, token.end_ms)

      // 若到达句末标记，落段并清空缓冲
      if (token.text === '<end>' || token.text === '<fin>') {
        commitSpeakerSegment(speaker)
        store.currentSegment = null
      }
    } else {
      nonFinalPreview.set(speaker, (nonFinalPreview.get(speaker) || '') + (token.text || ''))
      // 更新结束时间（用于预估显示）
      if (token.end_ms !== undefined) utterEndMs.set(speaker, token.end_ms)
    }
  }

  // 更新实时预览：最终缓冲 + 本帧非最终
  if (lastSpeakerInFrame) {
    const finalText = finalBySpeaker.get(lastSpeakerInFrame) || ''
    const preview = nonFinalPreview.get(lastSpeakerInFrame) || ''
    store.currentSegment = {
      speaker: lastSpeakerInFrame,
      text: mergeWithOverlap(finalText, preview),
    }
  }

  // 将本帧的非最终预览缓存到跨帧 Map，用于说话人切换时也能落段
  for (const [spk, pv] of nonFinalPreview.entries()) {
    previewBySpeaker.set(spk, pv)
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
