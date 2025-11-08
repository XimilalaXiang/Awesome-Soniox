<template>
  <div class="card mb-6">
    <h2 class="text-2xl font-bold mb-6">配置</h2>

    <!-- Soniox 配置 -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold mb-3">Soniox API</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-sm font-medium mb-1">API Key</label>
          <input
            v-model="localSonioxConfig.api_key"
            type="password"
            :placeholder="sonioxHasKey ? '已保存（留空保持不变）' : '输入 Soniox API Key'"
            class="input w-full"
          />
          <p v-if="sonioxHasKey" class="text-xs text-gray-500 mt-1">当前已保存密钥。留空表示不修改。</p>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">模型</label>
          <select v-model="localSonioxConfig.model" class="input w-full">
            <option value="stt-rt-v3">stt-rt-v3 (推荐)</option>
            <option value="stt-rt-preview">stt-rt-preview</option>
          </select>
        </div>
        <div class="flex items-center">
          <input
            v-model="localSonioxConfig.enable_speaker_diarization"
            type="checkbox"
            id="speaker-diarization"
            class="mr-2 w-5 h-5"
          />
          <label for="speaker-diarization" class="text-sm font-medium">
            启用发言人识别
          </label>
        </div>
      </div>
    </div>

    <!-- OpenAI 配置 -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold mb-3">OpenAI 兼容 API</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-sm font-medium mb-1">API URL</label>
          <input
            v-model="localOpenAIConfig.api_url"
            type="text"
            placeholder="https://api.openai.com/v1"
            class="input w-full"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">API Key</label>
          <input
            v-model="localOpenAIConfig.api_key"
            type="password"
            :placeholder="openaiHasKey ? '已保存（留空保持不变）' : '输入 OpenAI API Key'"
            class="input w-full"
          />
          <p v-if="openaiHasKey" class="text-xs text-gray-500 mt-1">当前已保存密钥。留空表示不修改。</p>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">模型</label>
          <input
            v-model="localOpenAIConfig.model"
            type="text"
            placeholder="gpt-4o-mini"
            class="input w-full"
          />
        </div>
      </div>
    </div>

    <!-- 保存按钮 -->
    <div class="flex justify-end">
      <button @click="saveConfig" class="btn-primary">
        保存配置
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'

const store = useTranscriptionStore()

const localSonioxConfig = ref({
  api_key: '',
  model: 'stt-rt-v3',
  enable_speaker_diarization: true,
  enable_language_identification: false,
  language_hints: []
})

const localOpenAIConfig = ref({
  api_url: 'https://api.openai.com/v1',
  api_key: '',
  model: 'gpt-4o-mini'
})

const sonioxHasKey = ref(false)
const openaiHasKey = ref(false)

onMounted(async () => {
  try {
    // 从云端加载配置
    const r = await fetch('/api/config', { credentials: 'include' })
    if (r.ok) {
      const data = await r.json()
      if (data.soniox_config) {
        localSonioxConfig.value = { ...localSonioxConfig.value, ...data.soniox_config }
        sonioxHasKey.value = !!data.soniox_config.has_api_key
      } else {
        localSonioxConfig.value = { ...store.sonioxConfig }
      }
      if (data.openai_config) {
        localOpenAIConfig.value = { ...localOpenAIConfig.value, ...data.openai_config }
        openaiHasKey.value = !!data.openai_config.has_api_key
      } else {
        localOpenAIConfig.value = { ...store.openaiConfig }
      }
    } else {
      // 回退到本地
      localSonioxConfig.value = { ...store.sonioxConfig }
      localOpenAIConfig.value = { ...store.openaiConfig }
    }
  } catch (_) {
    localSonioxConfig.value = { ...store.sonioxConfig }
    localOpenAIConfig.value = { ...store.openaiConfig }
  }
})

function saveConfig() {
  // 本地持久化（作为离线回退）
  store.saveSonioxConfig(localSonioxConfig.value)
  store.saveOpenAIConfig(localOpenAIConfig.value)
  // 云端保存
  const sonioxPayload = { ...localSonioxConfig.value }
  if (!sonioxPayload.api_key) delete sonioxPayload.api_key
  const openaiPayload = { ...localOpenAIConfig.value }
  if (!openaiPayload.api_key) delete openaiPayload.api_key
  fetch('/api/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      soniox_config: sonioxPayload,
      openai_config: openaiPayload
    })
  })
    .then((res) => res.json())
    .then(() => {
      alert('配置已保存（云端同步）！')
    })
    .catch(() => {
      alert('配置已保存（本地）。云端同步失败。')
    })
}
</script>
