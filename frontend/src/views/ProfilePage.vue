<template>
  <div style="max-width: 600px; margin: 0 auto; padding: 24px">
    <a-card title="个人信息" style="margin-bottom: 24px">
      <a-descriptions :column="1">
        <a-descriptions-item label="用户名">{{ auth.user?.username }}</a-descriptions-item>
        <a-descriptions-item label="邮箱">{{ auth.user?.email || '未设置' }}</a-descriptions-item>
        <a-descriptions-item label="角色"><a-tag>{{ auth.user?.role }}</a-tag></a-descriptions-item>
      </a-descriptions>
    </a-card>
    <a-card title="修改密码">
      <a-form layout="vertical">
        <a-form-item label="原密码"><a-input-password v-model:value="oldPassword" /></a-form-item>
        <a-form-item label="新密码"><a-input-password v-model:value="newPassword" /></a-form-item>
        <a-form-item label="确认新密码"><a-input-password v-model:value="confirmPassword" /></a-form-item>
        <a-button type="primary" :loading="loading" @click="changePassword">保存</a-button>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/store/auth'
import { post } from '@/api/request'

const auth = useAuthStore()
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)

const changePassword = async () => {
  if (newPassword.value !== confirmPassword.value) { message.error('两次密码不一致'); return }
  loading.value = true
  try {
    await post('/auth/change-password', { old_password: oldPassword.value, new_password: newPassword.value })
    message.success('密码已修改')
    oldPassword.value = ''; newPassword.value = ''; confirmPassword.value = ''
  } catch (e: any) { message.error(e.message || '修改失败') }
  finally { loading.value = false }
}
</script>
