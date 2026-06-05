<template>
  <a-config-provider :theme="{ token: { colorPrimary: '#c41d1d' } }">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store/auth';
import { onMounted } from 'vue';

const authStore = useAuthStore();

onMounted(() => {
  authStore.restoreFromStorage();
});
</script>
