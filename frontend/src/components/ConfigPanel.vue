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
            placeholder="输入 Soniox API Key"
            class="input w-full"
          />
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
            placeholder="输入 OpenAI API Key"
            class="input w-full"
          />
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

onMounted(() => {
  localSonioxConfig.value = { ...store.sonioxConfig }
  localOpenAIConfig.value = { ...store.openaiConfig }
})

function saveConfig() {
  store.saveSonioxConfig(localSonioxConfig.value)
  store.saveOpenAIConfig(localOpenAIConfig.value)
  alert('配置已保存！')
}
</script>
