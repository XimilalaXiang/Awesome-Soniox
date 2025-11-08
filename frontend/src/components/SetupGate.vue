<template>
  <div class="min-h-screen flex items-center justify-center bg-white">
    <div class="w-full max-w-sm border-4 border-black rounded-lg p-6">
      <h1 class="text-2xl font-bold mb-4">初始化密码</h1>
      <p class="text-sm text-gray-600 mb-4">首次使用，请设置访问密码。</p>
      <input
        v-model="pwd1"
        :disabled="loading"
        type="password"
        placeholder="新密码（至少4位）"
        class="input w-full mb-3"
      />
      <input
        v-model="pwd2"
        :disabled="loading"
        type="password"
        placeholder="确认新密码"
        class="input w-full mb-4"
      />
      <button class="btn-primary w-full" :disabled="loading || !canSubmit" @click="setup">
        {{ loading ? '设置中...' : '设置密码并进入' }}
      </button>
      <p v-if="error" class="text-red-600 text-sm mt-3">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const pwd1 = ref('')
const pwd2 = ref('')
const loading = ref(false)
const error = ref('')

const canSubmit = computed(() => pwd1.value && pwd1.value.length >= 4 && pwd1.value === pwd2.value)

async function setup() {
  if (!canSubmit.value) return
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch('/api/auth/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ password: pwd1.value })
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok || !data.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`)
    }
    window.location.reload()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}
</script>


