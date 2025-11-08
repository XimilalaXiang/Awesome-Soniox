<template>
  <component :is="viewComp" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterView } from 'vue-router'
import LoginGate from '@/components/LoginGate.vue'
import SetupGate from '@/components/SetupGate.vue'

const viewComp = ref(LoginGate)
onMounted(async () => {
  try {
    const r = await fetch('/api/auth/status', { credentials: 'include' })
    const data = await r.json().catch(() => ({}))
    if (data && data.setup) {
      viewComp.value = SetupGate
    } else if (data && data.ok) {
      viewComp.value = RouterView
    } else {
      viewComp.value = LoginGate
    }
  } catch (_) {
    viewComp.value = LoginGate
  }
})
</script>

<style>
@import './assets/main.css';
</style>
