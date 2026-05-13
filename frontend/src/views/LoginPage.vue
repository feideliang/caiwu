<template>
  <div class="login-page">
    <a-card class="login-card" :bordered="false">
      <div class="login-header">
        <h1>数智化财务管报系统</h1>
        <p>AI + BI 智能财务分析平台</p>
      </div>
      <a-form
        :model="formState"
        :rules="rules"
        :label-col="{ span: 0 }"
        :wrapper-col="{ span: 24 }"
        @finish="handleLogin"
      >
        <a-form-item name="username">
          <a-input
            v-model:value="formState.username"
            placeholder="用户名"
            size="large"
            :prefix="h(UserOutlined)"
          />
        </a-form-item>
        <a-form-item name="password">
          <a-input-password
            v-model:value="formState.password"
            placeholder="密码"
            size="large"
            :prefix="h(LockOutlined)"
          />
        </a-form-item>
        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            block
            :loading="loading"
          >
            登录
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, h, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/store/auth';
import { UserOutlined, LockOutlined } from '@ant-design/icons-vue';
import { message } from 'ant-design-vue';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const loading = ref(false);

const formState = reactive({
  username: '',
  password: '',
});

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
};

async function handleLogin() {
  loading.value = true;
  try {
    await authStore.login(formState.username, formState.password);
    message.success('登录成功');
    const redirect = (route.query.redirect as string) || '/';
    router.push(redirect);
  } catch (e: unknown) {
    const err = e as { response?: { status?: number }; message?: string };
    if (err.response?.status === 401) {
      message.error('用户名或密码错误');
    } else {
      message.error(err.message || '登录失败');
    }
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (route.query.expired === '1') {
    message.warning('登录已过期，请重新登录');
  }
});
</script>

<style scoped lang="less">
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);

  .login-header {
    text-align: center;
    margin-bottom: 32px;

    h1 {
      font-size: 24px;
      font-weight: 600;
      margin-bottom: 8px;
      color: var(--color-text);
    }

    p {
      font-size: 14px;
      color: var(--color-text-secondary);
      margin: 0;
    }
  }
}

@media (max-width: 767px) {
  .login-card {
    width: 90vw;
    max-width: 400px;
  }
}
</style>
