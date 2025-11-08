<template>
  <div class="min-h-screen flex items-center justify-center bg-white">
    <div class="w-full max-w-sm border-4 border-black rounded-lg p-6">
      <h1 class="text-2xl font-bold mb-4">访问验证</h1>
      <p class="text-sm text-gray-600 mb-4">请输入访问密码以进入系统。</p>
      <input
        v-model="password"
        :disabled="loading"
        type="password"
        placeholder="访问密码"
        class="input w-full mb-3"
        @keyup.enter="login"
      />
      <button class="btn-primary w-full" :disabled="loading || !password" @click="login">
        {{ loading ? '验证中...' : '进入' }}
      </button>
      <p v-if="error" class="text-red-600 text-sm mt-3">{{ error }}</p>
    </div>
  </div>
  </template>

<script setup>
import { ref } from 'vue'

const password = ref('')
const error = ref('')
const loading = ref(false)

async function login() {
  if (!password.value) return
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ password: password.value })
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
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


