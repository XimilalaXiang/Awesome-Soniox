<template>
  <div class="card">
    <h2 class="text-2xl font-bold mb-4">AI 助手</h2>

    <div v-if="!store.hasTranscript" class="text-center text-gray-400 py-8">
      开始录音后即可使用 AI 助手功能
    </div>

    <div v-else>
      <!-- 快捷操作 -->
      <div class="mb-4">
        <h3 class="text-sm font-semibold mb-2">快捷操作</h3>
        <div class="flex flex-wrap gap-2">
          <button
            @click="summarize"
            :disabled="isProcessing"
            class="btn-secondary text-sm"
          >
            📝 总结要点
          </button>
          <button
            @click="summarizeByTopic"
            :disabled="isProcessing"
            class="btn-secondary text-sm"
          >
            📋 按主题总结
          </button>
          <button
            @click="extractActionItems"
            :disabled="isProcessing"
            class="btn-secondary text-sm"
          >
            ✅ 提取待办事项
          </button>
        </div>
      </div>

      <!-- 自定义提问 -->
      <div class="mb-4">
        <h3 class="text-sm font-semibold mb-2">自定义提问</h3>
        <div class="flex space-x-2">
          <input
            v-model="customQuestion"
            @keyup.enter="askCustomQuestion"
            type="text"
            placeholder="输入你的问题..."
            class="input flex-1"
            :disabled="isProcessing"
          />
          <button
            @click="askCustomQuestion"
            :disabled="isProcessing || !customQuestion"
            class="btn-primary"
          >
            提问
          </button>
        </div>
      </div>

      <!-- AI 响应 -->
      <div v-if="aiResponse || isProcessing" class="mt-6">
        <h3 class="text-sm font-semibold mb-2">AI 回复</h3>
        <div class="border-2 border-black rounded-lg p-4 bg-gray-50 min-h-[100px] max-h-[400px] overflow-y-auto">
          <div v-if="isProcessing && !aiResponse" class="flex items-center text-gray-500">
            <div class="loading-dots mr-2">
              <span></span>
              <span></span>
              <span></span>
            </div>
            思考中...
          </div>
          <div v-else v-html="aiHtml"></div>
          <div v-if="isProcessing" class="inline-block">
            <span class="animate-pulse">▋</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'
import { summarizeSession, askQuestion } from '@/services/api'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const store = useTranscriptionStore()
const isProcessing = ref(false)
const aiResponse = ref('')
const customQuestion = ref('')

// Markdown 渲染
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const aiHtml = computed(() => {
  try {
    const html = md.render(aiResponse.value || '')
    return DOMPurify.sanitize(html)
  } catch (e) {
    return (aiResponse.value || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
})

async function summarize() {
  await processRequest('请总结以下会议内容的要点，以清晰的列表形式呈现：')
}

async function summarizeByTopic() {
  await processRequest('请按照讨论的主题对以下会议内容进行分类总结：')
}

async function extractActionItems() {
  await processRequest('请从以下会议内容中提取所有的待办事项、行动项和决策：')
}

async function askCustomQuestion() {
  if (!customQuestion.value.trim()) return
  await processRequest(customQuestion.value)
  customQuestion.value = ''
}

async function processRequest(prompt) {
  if (!store.openaiConfig.api_key) {
    alert('请先配置 OpenAI API')
    return
  }

  isProcessing.value = true
  aiResponse.value = ''

  try {
    // 使用流式 API
    const generator = summarizeSession(
      store.sessionId,
      store.openaiConfig,
      prompt
    )

    for await (const chunk of generator) {
      aiResponse.value += chunk
    }
  } catch (error) {
    console.error('AI processing error:', error)
    aiResponse.value = `错误: ${error.message}`
  } finally {
    isProcessing.value = false
  }
}
</script>

<style scoped>
.loading-dots span {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin: 0 2px;
  background-color: #666;
  border-radius: 50%;
  animation: loading 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes loading {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}
</style>
