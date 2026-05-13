<template>
  <div class="mobile-no-drill">
    <a-result
      status="info"
      icon="mobile"
      title="移动端不支持数据钻取"
      sub-title="钻取分析功能需要较大的屏幕空间，请在平板或电脑上使用"
    >
      <template #icon>
        <MobileOutlined style="font-size: 64px; color: var(--color-primary)" />
      </template>
      <template #extra>
        <a-button type="primary" @click="goBack">
          返回总览
        </a-button>
      </template>
    </a-result>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { MobileOutlined } from '@ant-design/icons-vue';
import { message } from 'ant-design-vue';

const router = useRouter();

onMounted(() => {
  message.info('移动端暂不支持数据钻取功能');
});

function goBack() {
  router.push({ name: 'Dashboard' });
}
</script>

<style scoped lang="less">
.mobile-no-drill {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
</style>
