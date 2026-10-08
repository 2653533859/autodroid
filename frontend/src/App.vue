<script setup>
import { RouterView } from 'vue-router'
import { watchEffect } from 'vue'
import { useClientMode } from '@/composables/useClientMode'

const { isMobileMode } = useClientMode()
watchEffect(() => document.body.classList.toggle('ad-mobile', isMobileMode.value))
</script>

<template>
  <RouterView />
</template>
