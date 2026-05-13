<template>
  <div>
    <a-space direction="vertical" style="width: 100%" :size="12">
      <a-space wrap>
        <a-select v-model:value="selectedSourceId" style="width: 260px" placeholder="选择数据源（可选）">
          <a-select-option :value="undefined">不指定</a-select-option>
          <a-select-option v-for="source in excelSources" :key="source.id" :value="source.id">
            {{ source.name }}
          </a-select-option>
        </a-select>
        <a-select v-model:value="selectedSyncMode" style="width: 140px" placeholder="同步模式">
          <a-select-option value="full">全量</a-select-option>
          <a-select-option value="incremental">增量</a-select-option>
        </a-select>
      </a-space>
    <a-upload-dragger v-model:fileList="fileList" :before-upload="beforeUpload" accept=".xlsx,.xls" :show-upload-list="false">
      <p class="ant-upload-drag-icon"><i class="anticon anticon-inbox" /></p>
      <p class="ant-upload-text">拖拽或点击上传 Excel 文件</p>
    </a-upload-dragger>
    <a-button type="primary" :loading="uploading" :disabled="!fileList.length" @click="handleUpload" style="margin-top: 16px">上传</a-button>
    <a-empty v-if="!result && !uploading" description="请选择 Excel 文件上传" style="margin-top: 32px" />
    <a-card v-if="result" title="上传结果" style="margin-top: 16px">
      <a-descriptions :column="2">
        <a-descriptions-item label="文件名">{{ result.filename }}</a-descriptions-item>
        <a-descriptions-item label="解析行数">{{ result.rows_parsed }}</a-descriptions-item>
        <a-descriptions-item label="清洗行数">{{ result.rows_cleaned }}</a-descriptions-item>
        <a-descriptions-item label="同步行数">{{ result.rows_synced }}</a-descriptions-item>
      </a-descriptions>
      <a-alert v-for="(err, i) in (result.errors || [])" :key="i" type="error" :message="err" style="margin-top: 8px" />
    </a-card>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { getDataSources, uploadExcel, type DataSourceItem } from '../../api/dataManagement'

const fileList = ref<any[]>([])
const uploading = ref(false)
const result = ref<any>(null)
const sources = ref<DataSourceItem[]>([])
const selectedSourceId = ref<number | undefined>(undefined)
const selectedSyncMode = ref<string>('incremental')

const excelSources = computed(() => sources.value.filter((s) => s.source_type === 'excel'))

const beforeUpload = (file: File) => { fileList.value = [{ originFileObj: file }]; return false }
const handleUpload = async () => {
  if (!fileList.value.length) return
  uploading.value = true
  try {
    const r = await uploadExcel(fileList.value[0].originFileObj, selectedSourceId.value, selectedSyncMode.value)
    result.value = r.data?.data
    message.success('上传成功')
    fileList.value = []
  } catch (e: any) { message.error(e.message || '上传失败') }
  finally { uploading.value = false }
}

onMounted(async () => {
  try {
    const { data } = await getDataSources()
    sources.value = (data.data as { items?: DataSourceItem[] })?.items || []
  } catch {}
})
</script>
