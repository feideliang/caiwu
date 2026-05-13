import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as apiLogin, getMe } from '@/api/auth';
import router from '@/router';
import type { User, UserRole } from '@/types/api';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const token = ref<string>(localStorage.getItem('access_token') || '');

  const isLoggedIn = computed(() => !!token.value);
  const role = computed<UserRole>(() => user.value?.role || 'viewer');
  const isAdmin = computed(() => role.value === 'admin');
  const isAnalyst = computed(() => role.value === 'analyst' || role.value === 'admin');
  const isViewer = computed(() => role.value === 'viewer');

  async function login(username: string, password: string) {
    const { data } = await apiLogin({ username, password });
    token.value = data.data.access_token;
    user.value = data.data.user;
    localStorage.setItem('access_token', token.value);
    localStorage.setItem('user', JSON.stringify(user.value));
  }

  async function fetchUser() {
    if (!token.value) return;
    try {
      const { data } = await getMe();
      user.value = data.data;
      localStorage.setItem('user', JSON.stringify(user.value));
    } catch {
      logout(true);
    }
  }

  function logout(sessionExpired = false) {
    token.value = '';
    user.value = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    const redirectPath = sessionExpired ? '/login?expired=1' : '/login';
    router.push(redirectPath);
  }

  function restoreFromStorage() {
    const stored = localStorage.getItem('user');
    if (stored && token.value) {
      try {
        user.value = JSON.parse(stored);
      } catch {
        logout();
      }
    }
  }

  return { user, token, isLoggedIn, role, isAdmin, isAnalyst, isViewer, login, fetchUser, logout, restoreFromStorage };
});
