<template>
  <div>
    <a-alert v-if="!auth.user || auth.user.role !== 'admin'" type="error" message="权限不足，仅管理员可访问" banner style="margin-bottom: 16px" />
    <a-tabs v-else default-active-key="users" @change="onTabChange">
      <a-tab-pane key="users" tab="用户管理">
        <a-button type="primary" @click="userModal = true" style="margin-bottom: 16px">添加用户</a-button>
        <a-table :dataSource="users" :loading="loadings.users" rowKey="id">
          <a-table-column title="用户名" dataIndex="username" />
          <a-table-column title="邮箱" dataIndex="email" />
          <a-table-column title="角色" dataIndex="role"><template #default="{ text }"><a-tag>{{ text }}</a-tag></template></a-table-column>
	          <a-table-column title="事业部" dataIndex="department" key="department" />
          <a-table-column title="操作"><template #default="{ record }"><a-button type="link" danger @click="handleDeleteUser(record.id)">删除</a-button></template></a-table-column>
        </a-table>
        <a-modal v-model:visible="userModal" title="添加用户" @ok="handleCreateUser">
          <a-form layout="vertical">
            <a-form-item label="用户名"><a-input v-model:value="newUser.username" /></a-form-item>
            <a-form-item label="密码"><a-input-password v-model:value="newUser.password" /></a-form-item>
            <a-form-item label="邮箱"><a-input v-model:value="newUser.email" /></a-form-item>
            <a-form-item label="角色"><a-select v-model:value="newUser.role_id"><a-select-option :value="2">分析师</a-select-option><a-select-option :value="3">观察者</a-select-option></a-select></a-form-item>
	            <a-form-item label="事业部" name="department"><a-input v-model:value="newUser.department" placeholder="例如: CBG" /></a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>
      <a-tab-pane key="datasources" tab="数据源"><DataSourceList /></a-tab-pane>
      <a-tab-pane key="emailsync" tab="邮件同步"><EmailSyncPanel /></a-tab-pane>
      <a-tab-pane key="quality" tab="数据质量"><DataQualityDashboard /></a-tab-pane>
      <a-tab-pane key="rules" tab="规则管理">
        <div style="margin-bottom: 16px; display: flex; gap: 8px">
          <a-button type="primary" @click="openRuleModal()">添加规则</a-button>
          <a-button @click="importModal = true">批量导入</a-button>
            <a-select v-model:value="ruleFilter" style="width: 160px" placeholder="按分类筛选" allow-clear @change="loadRules">
              <a-select-option value="gross_margin_change_analysis">毛利率变动分析</a-select-option>
              <a-select-option value="market_line_analysis">市场线分析</a-select-option>
              <a-select-option value="margin_health">毛利健康度</a-select-option>
              <a-select-option value="monthly_trend">月度趋势</a-select-option>
              <a-select-option value="yoy_mom_compare">同比环比分析</a-select-option>
              <a-select-option value="period_filter_rules">周期筛选规则</a-select-option>
              <a-select-option value="product_structure_analysis">产品结构分析</a-select-option>
              <a-select-option value="department_performance">部门绩效分析</a-select-option>
              <a-select-option value="customer_structure_analysis">客户结构分析</a-select-option>
              <a-select-option value="report_structure">报告结构</a-select-option>
            </a-select>
        </div>
        <a-table :dataSource="rules" :loading="loadings.rules" rowKey="id" size="small">
          <a-table-column title="分类" dataIndex="category" width="160"><template #default="{ text }"><a-tag>{{ text }}</a-tag></template></a-table-column>
          <a-table-column title="规则内容" dataIndex="rule_text" />
          <a-table-column title="来源" dataIndex="source_section" width="120" />
          <a-table-column title="状态" dataIndex="is_active" width="70"><template #default="{ text }"><a-tag :color="text ? 'green' : 'red'">{{ text ? '启用' : '禁用' }}</a-tag></template></a-table-column>
          <a-table-column title="操作" width="140">
            <template #default="{ record }">
              <a-button type="link" size="small" @click="openRuleModal(record)">编辑</a-button>
              <a-button type="link" size="small" danger @click="handleDeleteRule(record.id)">删除</a-button>
            </template>
          </a-table-column>
        </a-table>
        <a-modal v-model:visible="ruleModalVisible" :title="editingRule ? '编辑规则' : '添加规则'" @ok="handleSaveRule" width="600">
          <a-form layout="vertical">
            <a-form-item label="分类"><a-input v-model:value="ruleForm.category" placeholder="如: anomaly_gross_margin" /></a-form-item>
            <a-form-item label="规则内容"><a-textarea v-model:value="ruleForm.rule_text" :rows="4" /></a-form-item>
            <a-form-item label="来源章节"><a-input v-model:value="ruleForm.source_section" /></a-form-item>
            <a-form-item label="状态"><a-switch v-model:checked="ruleForm.is_active" checked-children="启用" un-checked-children="禁用" /></a-form-item>
          </a-form>
        </a-modal>
        <a-modal v-model:visible="importModal" title="批量导入规则" @ok="handleImport" width="600">
          <p>粘贴 JSON 数组格式的规则：</p>
          <a-textarea v-model:value="importText" :rows="10" placeholder='[{"category":"anomaly_gross_margin","rule_text":"...","source_section":"...","is_active":true}]' />
        </a-modal>
      </a-tab-pane>
      <a-tab-pane key="upload" tab="Excel上传"><ExcelUploader /></a-tab-pane>
      <a-tab-pane key="audit" tab="审计日志">
        <a-table :dataSource="auditLogs" :loading="loadings.logs" rowKey="id">
          <a-table-column title="用户ID" dataIndex="user_id" />
          <a-table-column title="操作" dataIndex="action"><template #default="{ text }"><a-tag>{{ text }}</a-tag></template></a-table-column>
          <a-table-column title="资源" dataIndex="resource_type" />
          <a-table-column title="时间" dataIndex="created_at" />
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { message, Modal } from 'ant-design-vue'
import { getUsers, createUser, deleteUser, getAuditLogs } from '@/api/dataManagement'
import { listRules, createRule, updateRule, deleteRule, importRules } from '@/api/rules'
import DataSourceList from '@/components/admin/DataSourceList.vue'
import EmailSyncPanel from '@/components/admin/EmailSyncPanel.vue'
import DataQualityDashboard from '@/components/admin/DataQualityDashboard.vue'
import ExcelUploader from '@/components/admin/ExcelUploader.vue'

const router = useRouter()
const auth = useAuthStore()
if (!auth.user || auth.user.role !== 'admin') router.replace('/')

const users = ref<any[]>([])
const auditLogs = ref<any[]>([])
const rules = ref<any[]>([])
const loadings = ref({ users: false, logs: false, rules: false })
const userModal = ref(false)
const newUser = ref({ username: '', password: '', email: '', role_id: 2, department: '' })

// Rules management
const ruleFilter = ref<string | undefined>(undefined)
const ruleModalVisible = ref(false)
const editingRule = ref<any>(null)
const ruleForm = ref({ category: '', rule_text: '', source_section: '', is_active: true })
const importModal = ref(false)
const importText = ref('')

const loadRules = async () => {
  loadings.value.rules = true
  try {
    const r = await listRules(ruleFilter.value || undefined)
    rules.value = (r.data?.data as any[]) || []
  } catch (e) { console.error('loadRules failed', e) } finally { loadings.value.rules = false }
}
const openRuleModal = (record?: any) => {
  editingRule.value = record || null
  ruleForm.value = record
    ? { category: record.category, rule_text: record.rule_text, source_section: record.source_section, is_active: record.is_active }
    : { category: '', rule_text: '', source_section: '', is_active: true }
  ruleModalVisible.value = true
}
const handleSaveRule = async () => {
  try {
    if (editingRule.value) {
      await updateRule(editingRule.value.id, ruleForm.value)
      message.success('规则已更新')
    } else {
      await createRule(ruleForm.value)
      message.success('规则已创建')
    }
    ruleModalVisible.value = false
    await loadRules()
  } catch (e) {
    console.error('handleSaveRule failed', e)
    message.error('保存失败，请重试')
  }
}
const handleDeleteRule = (id: number) => {
  Modal.confirm({ title: '确认删除此规则？', onOk: async () => { await deleteRule(id); message.success('已删除'); await loadRules() } })
}
const handleImport = async () => {
  try {
    const parsed = JSON.parse(importText.value)
    if (!Array.isArray(parsed)) throw new Error('Expected JSON array')
    const r = await importRules(parsed)
    message.success(`已导入 ${(r.data?.data as any)?.imported_count || 0} 条规则`)
    importModal.value = false
    importText.value = ''
    await loadRules()
  } catch (e: any) {
    message.error(`导入失败：${e.message}`)
  }
}

const loadUsers = async () => {
  loadings.value.users = true
  try { const r = await getUsers(); users.value = (r.data?.data as { items?: any[] })?.items || [] } catch (e) { console.error('loadUsers failed', e) } finally { loadings.value.users = false }
}
const loadAuditLogs = async () => {
  loadings.value.logs = true
  try { const r = await getAuditLogs({ page: 1, page_size: 50 }); auditLogs.value = (r.data?.data as { items?: any[] })?.items || [] } catch (e) { console.error('loadAuditLogs failed', e) } finally { loadings.value.logs = false }
}
const onTabChange = (key: string) => { if (key === 'users') loadUsers(); if (key === 'audit') loadAuditLogs(); if (key === 'rules') loadRules() }
const handleCreateUser = async () => {
  try {
    await createUser(newUser.value)
    userModal.value = false; message.success('用户已创建')
    newUser.value = { username: '', password: '', email: '', role_id: 2, department: '' }
    await loadUsers()
  } catch (e) {
    console.error('handleCreateUser failed', e)
    message.error('创建用户失败，请重试')
  }
}
const handleDeleteUser = (id: number) => {
  Modal.confirm({ title: '确认删除用户？', onOk: async () => { await deleteUser(id); message.success('已删除'); await loadUsers() } })
}

onMounted(() => { loadUsers(); loadRules() })
</script>
