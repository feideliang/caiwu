# AI+BI 数智化财务管报系统 — 前端详细开发计划 (FE-001 ~ FE-017)

**编制日期：** 2026-05-08
**编制人：** Frontend Lead Engineer
**来源文档：** V4.0 Master Plan (`playful-reddy.md`), 前端方案调整报告, PM Remediation (`pm-remediation-tasklist-v3-1.md`)
**项目状态：** 新项目 (Greenfield)，尚无源代码
**前置约定：**
- 所有 API 路径统一使用 `/api/v1/` 前缀
- 三端自适应：web (1920x1080) / tablet (768x1024) / mobile (375x667)
- i18n/a11y 为 Phase 3 (P2)，本次计划中跳过
- 移动端钻取禁用 (per DEC-07)
- 配置管理走环境变量，Phase 1 无配置 UI (per DEC-04)

---

## 目录

1. [FE-001: Sidebar — 用户角色/菜单权限](#fe-001-sidebar--用户角色菜单权限)
2. [FE-002: AIChartRecommender 组件](#fe-002-aichartrecommender-组件)
3. [FE-003: InsightCard 组件](#fe-003-insightcard-组件)
4. [FE-004: AdvancedFilter 组件](#fe-004-advancedfilter-组件)
5. [FE-005: CorrelationAnalysis + CalibrationPanel](#fe-005-correlationanalysis--calibrationpanel)
6. [FE-006: DrillDown L1~L4 组件](#fe-006-drilldown-l1l4-组件)
7. [FE-007: FinancialOverview 组件改造](#fe-007-financialoverview-组件改造)
8. [FE-008/009/010: ReportCenter (异步任务 + 进度指示器 + 取消重试，合并)](#fe-008009010-reportcenter-合并实现)
9. [FE-011: TopBar 通知铃铛](#fe-011-topbar-通知铃铛)
10. [FE-012: 数据新鲜度指示器](#fe-012-数据新鲜度指示器)
11. [FE-013: Mobile 钻取禁用](#fe-013-mobile-钻取禁用)
12. [FE-014: 响应式布局验证](#fe-014-响应式布局验证)
13. [FE-015: TransactionAnalysis (Phase 2)](#fe-015-transactionanalysis-phase-2)
14. [FE-016: ForecastChart + ConfidenceBand](#fe-016-forecastchart--confidenceband)
15. [FE-017: DataSourceList / DataQualityDashboard / ExcelUploader (Phase 3)](#fe-017-datasourcelist--dataqualitydashboard--exceluploader-phase-3)

---

## FE-001: Sidebar — 用户角色/菜单权限

### 1. 组件结构

**文件路径：**
- `src/components/layout/Sidebar.vue` — 主组件
- `src/components/layout/SidebarItem.vue` — 子组件，递归渲染菜单项
- `src/composables/usePermission.ts` — 权限判断逻辑

**路由配置：**
- 基于 Vue Router 的导航守卫，在 `src/router/index.ts` 中配置 `beforeEach` 守卫

### 2. API 合同

**`GET /api/v1/auth/me`**

Response (200):
```typescript
interface AuthMeResponse {
  code: number;       // 0 = success
  message: string;
  data: {
    user_id: string;
    username: string;
    role: 'admin' | 'analyst' | 'viewer';
    permissions: string[];  // e.g. ['report:create', 'report:cancel', 'data:export']
    menus: MenuItem[];
  };
}

interface MenuItem {
  key: string;         // 路由 key，对应 route name
  label: string;       // 菜单显示名
  icon: string;        // ant-design icon name
  path: string;        // 路由路径
  children?: MenuItem[];
  permissions?: string[];  // 需要的权限，不传则人人可见
}
```

**`POST /api/v1/auth/login`**

Request:
```typescript
interface LoginRequest {
  username: string;
  password: string;
}
```

Response (200):
```typescript
interface LoginResponse {
  code: number;
  message: string;
  data: {
    token: string;       // JWT
    expires_in: number;  // 过期秒数
  };
}
```

Error (401):
```typescript
{ code: 401, message: "用户名或密码错误", data: null }
```

### 3. 状态管理

**Pinia Store: `src/stores/auth.ts`**

```typescript
// src/stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MenuItem } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'))
  const user = ref<AuthMeResponse['data'] | null>(null)
  const menus = ref<MenuItem[]>([])
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const role = computed(() => user.value?.role ?? 'viewer')
  const permissions = computed(() => user.value?.permissions ?? [])

  // actions
  async function login(username: string, password: string) { /* POST /api/v1/auth/login */ }
  async function fetchUserInfo() { /* GET /api/v1/auth/me */ }
  function logout() { /* clear token + user */ }
  function hasPermission(perm: string): boolean { return permissions.value.includes(perm) }

  return { token, user, menus, loading, isLoggedIn, role, permissions, login, fetchUserInfo, logout, hasPermission }
})
```

### 4. UI/UX 细节

**Sidebar.vue Props:**
```typescript
interface SidebarProps {
  collapsed: boolean;  // 折叠状态
  mode: 'web' | 'tablet' | 'mobile';
}
```

**三端形态：**
| 设备 | 侧边栏形态 | 菜单样式 |
|------|-----------|---------|
| web | 固定展开 (240px)，可折叠至 64px | 完整文字 + icon |
| tablet | 默认折叠为 icon 栏，hover 展开 (浮层) | 仅 icon，hover 显示提示 |
| mobile | 底部 Tab 导航 (4-5 个主菜单) | 仅 icon + 极短文字 |

**角色菜单矩阵：**
| 菜单项 | admin | analyst | viewer |
|--------|-------|---------|--------|
| 财务总览 (/) | visible | visible | visible |
| 关联分析 (/correlation) | visible | visible | visible |
| 钻取 (/drilldown) | visible | visible | visible (不可操作钻取) |
| 报告中心 (/reports) | visible | visible | visible |
| 预测分析 (/prediction) | visible | visible | visible |
| 交易分析 (/transactions) | visible | visible | hidden |
| 数据管理 (/data) | visible | hidden | hidden |

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 骨架屏，3 行灰色条
- **Error (401):** 跳转登录页
- **Error (network):** 显示 "加载失败，点击重试"
- **Edge:** token 过期时自动跳转登录页（通过 axios 拦截器 + 401 统一处理）
- **Edge:** viewer 无任何菜单时显示 "当前账号无访问权限"

### 5. 响应式行为

- web: `display: flex`, sidebar 240px, 可折叠
- tablet (768-1024px): sidebar 64px (icon only)，菜单文字通过 a-popover 展示
- mobile (<768px): sidebar 完全隐藏，底部 TabBar 组件 (`src/components/layout/MobileTabBar.vue`) 替代

### 6. 测试要求

**Unit Tests (Vitest, 6 用例):**
1. `usePermission` — hasPermission 正确判断权限
2. auth store — login 成功后 token 写入 localStorage
3. auth store — fetchUserInfo 解析 role/menus 正确
4. auth store — logout 清除全部状态
5. router guard — 无 token 跳转 /login
6. router guard — viewer 访问 /data 返回 403 页面

**E2E Tests (Playwright, 3 用例):**
1. admin 登录看到全部菜单项
2. viewer 登录看不到数据管理
3. 无 token 直接访问 /reports 跳转登录页

### 7. 依赖

- AR-013 (RBAC 权限系统)：后端 JWT + roles 表完成
- Vue Router 导航守卫
- Axios 拦截器 (401 统一处理)

---

## FE-002: AIChartRecommender 组件

### 1. 组件结构

**文件路径：**
- `src/components/ai/AIChartRecommender.vue` — 主组件
- `src/components/ai/RecommenderCard.vue` — 推荐项卡片
- `src/components/ai/RecommendationCarousel.vue` — 推荐项轮播 (移动端)
- `src/composables/useChartRecommend.ts` — 推荐逻辑 (规则预筛 + API 调用)

### 2. API 合同

**`POST /api/v1/ai/recommend-chart`**

Request:
```typescript
interface RecommendChartRequest {
  data_schema: {
    fields: Array<{
      name: string;
      data_type: 'numeric' | 'date' | 'categorical' | 'text';
      cardinality?: number;  // 唯一值数量
    }>;
    row_count: number;
  };
  data_features: string[];   // ['time_series', 'comparison', 'distribution', 'proportion', 'relationship']
  display_target: 'web' | 'tablet' | 'mobile';
}
```

Response (200):
```typescript
interface RecommendChartResponse {
  code: number;
  data: {
    recommendations: Array<{
      chart_type: string;      // 'line' | 'bar' | 'pie' | 'scatter' | 'radar' | 'sankey' | 'table'
      confidence: number;      // 0-1
      reason: string;          // AI 推荐理由
      echarts_option: object;  // 可直接使用的 ECharts option 片段
    }>;
  };
}
```

**`POST /api/v1/ai/recommend-layout`**

Request:
```typescript
interface RecommendLayoutRequest {
  charts: Array<{
    chart_type: string;
    priority: number;  // 重要性
  }>;
  display_target: 'web' | 'tablet' | 'mobile';
}
```

Response (200):
```typescript
interface RecommendLayoutResponse {
  code: number;
  data: {
    grid_layout: {
      columns: number;      // 列数
      rows: Array<{
        row_index: number;
        items: Array<{
          chart_index: number;
          col_span: number;  // 跨列数
          row_span: number;
        }>;
      }>;
    };
  };
}
```

### 3. 状态管理

**Pinia Store: `src/stores/recommend.ts`**

```typescript
export const useRecommendStore = defineStore('recommend', () => {
  const chartRecs = ref<RecommendChartResponse['data']['recommendations']>([])
  const layoutRec = ref<RecommendLayoutResponse['data']['grid_layout'] | null>(null)
  const activeChartIndex = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchChartRecommendations(dataSchema: DataSchema) { ... }
  async function fetchLayoutRecommendations(charts: ChartItem[]) { ... }
  function applyRecommendation(index: number) { /* emit layout change */ }

  return { chartRecs, layoutRec, activeChartIndex, loading, error, fetchChartRecommendations, fetchLayoutRecommendations, applyRecommendation }
})
```

### 4. UI/UX 细节

**AIChartRecommender.vue Props:**
```typescript
interface AIChartRecommenderProps {
  dataSchema: DataSchema;
  displayTarget: 'web' | 'tablet' | 'mobile';
  visible: boolean;  // 控制推荐面板显隐
}
```

**Events:**
```typescript
interface AIChartRecommenderEmits {
  (e: 'apply', chartConfig: { chartType: string; echartsOption: object }): void
  (e: 'apply-layout', layout: GridLayout): void
  (e: 'close'): void
}
```

**三端视觉：**
| 设备 | 推荐面板样式 |
|------|-------------|
| web | 右侧滑出面板，400px 宽 |
| tablet | 底部抽屉，可拖动关闭 |
| mobile | 全屏底部 sheet，横向滑动切换推荐项 |

**规则预筛 (前端 useChartRecommend.ts)：**
```typescript
function preScreenByRules(fields: Field[]): string[] {
  const types = fields.map(f => f.data_type)
  const hasDate = types.includes('date')
  const hasNumeric = types.filter(t => t === 'numeric').length >= 2
  const hasCategorical = types.includes('categorical')

  if (hasDate && hasNumeric) return ['line', 'area', 'bar']
  if (hasCategorical && hasNumeric) return ['bar', 'radar', 'pie']
  // ...
  return ['table']
}
```

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 推荐面板显示 3 个灰色卡片骨架屏 + 旋转动画文字 "AI 正在分析数据特征..."
- **Empty:** 无可推荐图表时显示 "暂无可推荐的可视化方案"，提供 fallback table 按钮
- **Error (API 失败):** 降级为纯规则引擎推荐，显示 "AI 推荐暂不可用，已使用规则推荐"
- **Edge:** data_schema 字段过多 (>20) 时截断，只分析前 20 个字段
- **Edge:** 规则预筛没有任何匹配时，强制返回 table 作为 fallback

### 5. 响应式行为

- 三端推荐面板宽度自适应 (400px / 全宽-32px / 全屏)
- 移动端轮播卡片支持 touch 滑动
- tablet 端抽屉支持拖拽关闭
- 推荐卡片数量：web 展示 top 8，tablet 展示 top 6，mobile 展示 top 4

### 6. 测试要求

**Unit Tests (5 用例):**
1. 规则预筛 — 时间序列字段返回 line/area/bar
2. 规则预筛 — 分类+数值字段返回 bar/radar/pie
3. 规则预筛 — 无匹配时返回 table fallback
4. recommend store — API 成功时 chartRecs 正确赋值
5. recommend store — API 失败时 error 设置 + 降级规则推荐

**E2E Tests (3 用例):**
1. 点击 AI 推荐按钮 → 面板展开 → 看到推荐卡片列表
2. 点击 "应用推荐" → 图表切换为推荐类型
3. 移动端推荐面板手势滑动切换

### 7. 依赖

- FE-007 (FinancialOverview 集成 AIChartRecommender)
- AR-001 (recommend-chart/recommend-layout API)

---

## FE-003: InsightCard 组件

### 1. 组件结构

**文件路径：**
- `src/components/ai/InsightCard.vue` — 单条洞察卡片
- `src/components/ai/InsightList.vue` — 洞察列表容器
- `src/composables/useInsights.ts` — 洞察状态管理 + API 调用

### 2. API 合同

**`GET /api/v1/insights?type=growth,risk&status=unread&page=1&page_size=20`**

Response (200):
```typescript
interface InsightsResponse {
  code: number;
  data: {
    items: InsightItem[];
    total: number;
    page: number;
    page_size: number;
  };
}

interface InsightItem {
  id: string;
  type: 'growth' | 'risk' | 'optimization' | 'anomaly';
  title: string;
  content: string;
  confidence: number;    // 0-1
  related_drill_path?: string;  // 关联钻取路径，如 "/drilldown/rep-001/dept-002"
  metrics?: Array<{ name: string; value: string; change?: string }>;
  timestamp: string;     // ISO 8601
  status: 'unread' | 'read' | 'processed' | 'ignored';
}
```

**`POST /api/v1/insights/{id}/status`**

Request:
```typescript
interface InsightStatusRequest {
  status: 'read' | 'processed' | 'ignored';
}
```

Response (200):
```typescript
{ code: 0, message: "ok", data: null }
```

### 3. 状态管理

**Pinia Store: `src/stores/insights.ts`**

```typescript
export const useInsightStore = defineStore('insights', () => {
  const items = ref<InsightItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const filters = ref({ type: '', status: 'unread', page: 1, page_size: 20 })

  const unreadCount = computed(() => items.value.filter(i => i.status === 'unread').length)

  async function fetchInsights() { /* GET /api/v1/insights */ }
  async function updateStatus(id: string, status: string) { /* POST /api/v1/insights/{id}/status */ }
  function setFilter(partial: Partial<typeof filters.value>) { /* merge filter + refetch */ }

  return { items, total, loading, filters, unreadCount, fetchInsights, updateStatus, setFilter }
})
```

### 4. UI/UX 细节

**InsightCard.vue Props:**
```typescript
interface InsightCardProps {
  insight: InsightItem;
  compact?: boolean;    // 紧凑模式 (用于侧边栏)
  showActions?: boolean; // 显示操作按钮
}
```

**Events:**
```typescript
interface InsightCardEmits {
  (e: 'status-change', id: string, status: string): void
  (e: 'drill-down', path: string): void
  (e: 'chart-link', metrics: string[]): void
}
```

**洞察类型视觉：**
| 类型 | Icon | 颜色 | 顶部边框色 |
|------|------|------|-----------|
| growth | ArrowUpOutlined | #52c41a (green) | green |
| risk | WarningOutlined | #faad14 (yellow) | yellow |
| optimization | BulbOutlined | #1890ff (blue) | blue |
| anomaly | AlertOutlined | #ff4d4f (red) | red |

**交互流程：**
1. 点击卡片展开详情 (含关联指标 mini chart)
2. "标记已处理"按钮 → 调用 POST status → 卡片灰化
3. "查看详情" → emit drill-down → 导航到钻取页
4. "忽略" → 调用 POST ignore → 卡片隐藏 (配合动画)
5. 图表联动：点击洞察中的指标 → emit chart-link → 主图表高亮相关区域

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 3 张灰色卡片骨架屏
- **Empty:** "暂无 AI 洞察，数据更新后将自动生成"
- **Error:** "洞察加载失败"，提供重试按钮
- **Edge:** 单页超过 50 条时自动分页 (无限滚动)
- **Edge:** 状态更新失败时乐观更新 + 回滚

### 5. 响应式行为

| 设备 | 展示方式 |
|------|---------|
| web | 右侧面板列表，每项 120px 高 |
| tablet | 底部面板网格 (2列) |
| mobile | 横向滑动卡片流 (snap-scroll)，每卡宽 280px |

### 6. 测试要求

**Unit Tests (4 用例):**
1. insight store — fetchInsights 正确解析分页数据
2. insight store — updateStatus 后本地状态更新
3. insight store — setFilter 合并参数后触发重新请求
4. InsightCard — 所有 4 种类型显示正确 icon 和颜色

**E2E Tests (3 用例):**
1. 查看洞察列表 → 点击"标记已处理" → 卡片灰化
2. 点击风险洞察中的"查看详情" → 跳转到钻取页
3. 点击洞察指标 → 主图表高亮对应区域

### 7. 依赖

- FE-006 (钻取跳转)
- FE-007 (FinancialOverview 集成)
- AR-001 (insights API)

---

## FE-004: AdvancedFilter 组件

### 1. 组件结构

**文件路径：**
- `src/components/filter/AdvancedFilter.vue` — 主组件
- `src/components/filter/FilterRow.vue` — 单行筛选条件
- `src/components/filter/FilterViewSaveModal.vue` — 保存视图弹窗
- `src/components/filter/FilterViewList.vue` — 已保存视图列表
- `src/composables/useFilter.ts` — 筛选逻辑 + DSL 生成

### 2. API 合同

**`GET /api/v1/filter-options`**

Response (200):
```typescript
interface FilterOptionsResponse {
  code: number;
  data: {
    date_range: { min: string; max: string };
    companies: Array<{ id: string; name: string }>;
    departments: Array<{ id: string; name: string; company_id: string }>;
    customer_types: Array<{ value: string; label: string }>;
    metrics: Array<{ key: string; name: string; unit: string }>;
    statuses: Array<{ value: string; label: string }>;
  };
}
```

**`POST /api/v1/query`**

Request:
```typescript
interface QueryRequest {
  dimensions: string[];       // 查询维度
  metrics: string[];          // 查询指标
  filters: FilterDSL;         // 筛选条件
  page?: number;
  page_size?: number;
  sort?: { field: string; order: 'asc' | 'desc' };
}

interface FilterDSL {
  logic: 'AND' | 'OR';
  conditions: Array<{
    field: string;
    operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'between' | 'contains';
    value: any;
  }>;
}
```

**`GET /api/v1/filter-views`** / **`POST /api/v1/filter-views`** / **`DELETE /api/v1/filter-views/{id}`**

```typescript
interface FilterView {
  id: string;
  name: string;
  filter_condition: FilterDSL;
  is_shared: boolean;
  created_at: string;
}
```

### 3. 状态管理

**Pinia Store: `src/stores/filter.ts`**

```typescript
export const useFilterStore = defineStore('filter', () => {
  const options = ref<FilterOptionsResponse['data'] | null>(null)
  const conditions = ref<FilterDSL['conditions']>([])
  const logic = ref<'AND' | 'OR'>('AND')
  const views = ref<FilterView[]>([])
  const recentSearches = ref<FilterDSL[]>([])  // 最多 5 条
  const loading = ref(false)

  const currentDSL = computed<FilterDSL>(() => ({ logic: logic.value, conditions: conditions.value }))

  async function fetchOptions() { /* GET /api/v1/filter-options */ }
  async function saveView(name: string) { /* POST /api/v1/filter-views */ }
  async function loadView(view: FilterView) { /* set conditions from view */ }
  async function deleteView(id: string) { /* DELETE /api/v1/filter-views/{id} */ }
  function addCondition(field: string, op: string, value: any) { conditions.value.push(...) }
  function removeCondition(index: number) { conditions.value.splice(index, 1) }
  function clearAll() { conditions.value = []; logic.value = 'AND' }
  function toggleLogic() { logic.value = logic.value === 'AND' ? 'OR' : 'AND' }

  return { options, conditions, logic, views, recentSearches, loading, currentDSL,
    fetchOptions, saveView, loadView, deleteView, addCondition, removeCondition, clearAll, toggleLogic }
})
```

### 4. UI/UX 细节

**AdvancedFilter.vue Props:**
```typescript
interface AdvancedFilterProps {
  filterConfig?: FilterField[];  // 自定义筛选项(不传则显示全部)
  compact?: boolean;  // 紧凑模式(侧边栏)
}
```

**筛选字段：**
| 字段 | 组件类型 | 级联 |
|------|---------|------|
| 时间范围 | DatePicker.RangePicker + 快捷选项 | 无 |
| 公司 | Select (多选/搜索) | 无 |
| 产品事业部 | Select (多选/搜索) | 依赖公司 |
| 客户类型 | Radio.Group | 无 |
| 指标维度 | Select (多选) | 无 |
| 状态 | Select | 无 |

**快捷时间选项：** 本周 / 本月 / 本季度 / 本年 / 自定义

**视图保存交互：**
1. 点击 "保存视图" → FilterViewSaveModal 弹窗
2. 输入名称，选择是否共享
3. 保存后视图出现在 FilterViewList 中
4. 点击视图名称一键应用
5. 视图可删除 (仅自己创建的)
6. 最近 5 条筛选条件自动保存 (localStorage)

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 选项加载时所有下拉框显示 loading 状态
- **Empty (options):** "选项加载失败"，显示重试按钮
- **Empty (views):** "暂无保存的筛选视图"
- **Edge:** 级联选项 — 选公司后事业部只显示该公司下属
- **Edge:** DSL 超过 10 个条件时提示 "建议简化筛选条件"
- **Edge:** IN 操作符超过 50 个值时提示 "建议缩小选择范围"

### 5. 响应式行为

| 设备 | 筛选形态 |
|------|---------|
| web | 顶部固定栏，水平展开所有筛选项 |
| tablet | 顶部固定栏，默认折叠，点击 "筛选" 按钮展开 |
| mobile | 底部抽屉面板 (MobileDrawer)，全屏，上下滚动 |

### 6. 测试要求

**Unit Tests (6 用例):**
1. filter store — addCondition 正确追加条件
2. filter store — toggleLogic 正确切换 AND/OR
3. filter store — clearAll 清空全部
4. useFilter — DSL 生成正确格式
5. useFilter — 级联过滤正确过滤子集
6. 视图保存/加载 round-trip

**E2E Tests (4 用例):**
1. 选择时间范围 + 公司 → 触发 query API
2. AND/OR 切换 → DSL 中 logic 字段变化
3. 保存视图 → 关闭页面 → 重新打开加载视图
4. 移动端筛选器从底部抽屉展开

### 7. 依赖

- FE-007 (FinancialOverview 使用筛选)
- FE-015 (TransactionAnalysis 使用筛选)
- AR-001 (filter-options/query/views API)

---

## FE-005: CorrelationAnalysis + CalibrationPanel

### 1. 组件结构

**文件路径：**
- `src/pages/CorrelationAnalysis.vue` — 页面容器
- `src/components/correlation/CorrelationMatrix.vue` — 相关性矩阵热力图
- `src/components/correlation/CorrelationDetail.vue` — 单对相关性详情
- `src/components/correlation/CalibrationPanel.vue` — 人工校准面板
- `src/composables/useCorrelation.ts` — 分析 + 校准逻辑

### 2. API 合同

**`POST /api/v1/correlations/analyze`**

Request:
```typescript
interface AnalyzeCorrelationRequest {
  metrics: string[];           // 要分析的指标列表
  date_range?: { start: string; end: string };
  method?: 'pearson' | 'spearman';  // 默认 pearson
}
```

Response (200):
```typescript
interface AnalyzeCorrelationResponse {
  code: number;
  data: {
    id: string;  // 分析批次 ID
    matrix: Array<{
      metric_a: string;
      metric_b: string;
      coefficient: number;     // -1 to 1
      p_value: number;
      ai_explanation: string;  // "AI推测：毛利率下降与应收账款周转天数增加存在强相关..."
      confidence_level: 'high' | 'medium' | 'low';
    }>;
    created_at: string;
  };
}
```

**`GET /api/v1/correlations`** — 获取历史分析结果 (分页)

**`POST /api/v1/correlations/{id}/calibrate`**

Request:
```typescript
interface CalibrateRequest {
  metric_a: string;
  metric_b: string;
  decision: 'confirm' | 'doubt' | 'reject';
  comment?: string;
}
```

Response (200):
```typescript
{ code: 0, message: "ok", data: null }
```

### 3. 状态管理

**Pinia Store: `src/stores/correlation.ts`**

```typescript
export const useCorrelationStore = defineStore('correlation', () => {
  const currentAnalysis = ref<AnalyzeCorrelationResponse['data'] | null>(null)
  const history = ref<CorrelationHistoryItem[]>([])
  const loading = ref(false)
  const selectedPair = ref<{ metricA: string; metricB: string } | null>(null)

  const matrixData = computed(() => {
    // 转换为热力图数据格式
    if (!currentAnalysis.value) return []
    return currentAnalysis.value.matrix.map(m => ({
      a: m.metric_a, b: m.metric_b,
      value: m.coefficient,
      confidence: m.confidence_level
    }))
  })

  async function analyze(metrics: string[]) { /* POST /api/v1/correlations/analyze */ }
  async function calibrate(id: string, req: CalibrateRequest) { /* POST /api/v1/correlations/{id}/calibrate */ }
  async function fetchHistory() { /* GET /api/v1/correlations */ }

  return { currentAnalysis, history, loading, selectedPair, matrixData, analyze, calibrate, fetchHistory }
})
```

### 4. UI/UX 细节

**CorrelationMatrix.vue Props:**
```typescript
interface CorrelationMatrixProps {
  data: Array<{ a: string; b: string; value: number; confidence: string }>;
  selectedPair?: { metricA: string; metricB: string } | null;
}
```

**Matrix 渲染：**
- ECharts 热力图，x/y 轴为指标名
- 颜色渐变：红 (-1) → 白 (0) → 蓝 (1)
- 每个格子显示系数值 (保留 2 位小数)
- 点击格子高亮该对，右侧显示详情
- 系数绝对值 >= 0.8 时格子加粗边框 (高置信度)

**CalibrationPanel.vue Props:**
```typescript
interface CalibrationPanelProps {
  pair: { metricA: string; metricB: string; coefficient: number; aiExplanation: string };
  calibrationHistory?: Array<{ decision: string; comment: string; timestamp: string }>;
}
```

**CalibrationPanel Events:**
```typescript
interface CalibrationPanelEmits {
  (e: 'calibrate', decision: 'confirm' | 'doubt' | 'reject', comment?: string): void
}
```

**校准交互：**
1. 展示 AI 解释文本 + "这是 AI 推测，请人工验证" 提示
2. 三个按钮：确认 (绿色) / 存疑 (黄色) / 否定 (红色)
3. 选择后弹出可选评论输入框
4. 校准后按钮变 disabled，展示 "已校准"
5. 校准历史折叠展示

**Loading/Empty/Error/Edge Cases:**
- **Loading (analyze):** 矩阵区域显示 "正在分析相关性..." 加载动画
- **Empty (no data):** "暂无相关分析数据，请选择指标进行分析"
- **Empty (history):** "暂无历史分析记录"
- **Error:** "分析失败" + 重试按钮
- **Edge:** 只有 1 个指标时禁用 "分析" 按钮，提示 "至少选择 2 个指标"
- **Edge:** p_value > 0.05 的结果默认折叠，标注 "统计不显著 (p>0.05)"

### 5. 响应式行为

| 设备 | 布局 |
|------|------|
| web | 左侧矩阵 60%，右侧详情面板 40%，并排 |
| tablet | 矩阵在上，详情在下，堆叠 |
| mobile | 矩阵全屏+可缩放 (拖拽/双指缩放)，详情底部 sheet |

### 6. 测试要求

**Unit Tests (5 用例):**
1. correlation store — analyze 正确解析矩阵数据
2. correlation store — calibrate 发送正确 payload
3. matrixData computed — 正确转换为热力图格式
4. 系数颜色映射正确
5. 置信度等级判定正确

**E2E Tests (4 用例):**
1. 选择指标 → 点击分析 → 矩阵渲染
2. 点击矩阵格子 → 右侧详情面板更新
3. 点击确认/存疑/否定 → 校准记录显示
4. 历史分析列表查看

### 7. 依赖

- FE-007 (页面路由)
- AR-009 (correlation API)

---

## FE-006: DrillDown L1~L4 组件

### 1. 组件结构

**文件路径：**
- `src/pages/drilldown/DrillDownContainer.vue` — 路由容器 (面包屑 + 禁用检测)
- `src/pages/drilldown/DrillDownL1Summary.vue` — L1 公司/集团层
- `src/pages/drilldown/DrillDownL2Department.vue` — L2 部门层
- `src/pages/drilldown/DrillDownL3Product.vue` — L3 产品/客户层
- `src/pages/drilldown/DrillDownL4Detail.vue` — L4 交易明细层
- `src/pages/drilldown/DrillDownRecordDetail.vue` — 单条记录详情弹窗
- `src/composables/useDrillDown.ts` — 钻取数据 + 面包屑逻辑

**路由配置：**
```typescript
// src/router/index.ts
{
  path: '/drilldown',
  component: DrillDownContainer,
  children: [
    { path: ':reportId',               name: 'DrillL1', component: DrillDownL1Summary },
    { path: ':reportId/:departmentId', name: 'DrillL2', component: DrillDownL2Department },
    { path: ':reportId/:departmentId/:productId', name: 'DrillL3', component: DrillDownL3Product },
    { path: ':reportId/:departmentId/:productId/:recordId', name: 'DrillL4', component: DrillDownL4Detail },
  ]
}
```

### 2. API 合同

**`GET /api/v1/drilldowns/{report_id}/summary`**

Response (200):
```typescript
interface DrillL1Response {
  code: number;
  data: {
    report_id: string;
    report_name: string;
    date_range: { start: string; end: string };
    kpis: Array<{
      name: string; value: number; unit: string;
      change: number; change_type: 'increase' | 'decrease' | 'flat';
      is_abnormal: boolean;
    }>;
    departments: Array<{
      id: string; name: string;
      revenue: number; revenue_share: number;
      is_abnormal: boolean;
    }>;
  };
}
```

**`GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products`**

**`GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products/{product_id}/records`**

**`GET /api/v1/drilldowns/records/{record_id}`** — 单条明细

### 3. 状态管理

**Pinia Store: `src/stores/drilldown.ts`**

```typescript
export const useDrillDownStore = defineStore('drilldown', () => {
  const currentLevel = ref(1)
  const breadcrumbs = ref<Array<{ label: string; path: string }>>([])
  const l1Data = ref<DrillL1Response['data'] | null>(null)
  // ... l2Data, l3Data, l4Data
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isL1Empty = computed(() => !l1Data.value || l1Data.value.kpis.length === 0)

  async function fetchL1(reportId: string) { /* GET /drilldowns/{report_id}/summary */ }
  async function fetchL2(reportId: string, deptId: string) { ... }
  async function fetchL3(reportId: string, deptId: string, prodId: string) { ... }
  async function fetchL4(reportId: string, deptId: string, prodId: string, recordId: string) { ... }
  function navigateUp(level: number) { /* 面包屑回退 */ }
  function updateBreadcrumbs(level: number, label: string) { ... }

  return { currentLevel, breadcrumbs, l1Data, loading, error, isL1Empty, /* l2,l3,l4 */, fetchL1, fetchL2, fetchL3, fetchL4, navigateUp, updateBreadcrumbs }
})
```

### 4. UI/UX 细节

**L1 汇总概览：**
- 顶部面包屑：报告名 > 汇总概览 (当前)
- 4 个 KPI 卡片：收入、利润、DSO、现金流
  - 每个显示数值 + 环比变化 + 异常标记 (红色角标)
  - KPI 点击展开 mini sparkline chart
- 部门列表表格：部门名 / 收入 / 占比 / 异常标记
- 点击部门行跳转 L2 (emit + router.push)

**L2 部门维度：**
- 面包屑：报告名 > 部门名 (当前)
- 部门 KPI 卡片
- 部门间对比柱状图 (ECharts)
- 异常部门高亮 (红色边框)
- 产品列表 → 点击跳转 L3

**L3 产品/客户维度：**
- 面包屑：报告名 > 部门名 > 产品名 (当前)
- 产品线收入分析图表
- 客户贡献排行 (Top 10)
- 产品-客户交叉分析矩阵
- 交易列表 → 点击跳转 L4

**L4 明细数据：**
- 面包屑：报告名 > 部门名 > 产品名 > 明细 (当前)
- 明细表格 (支持排序、筛选、分页)
- 导出 Excel 按钮
- 点击行弹出详情弹窗 (DrillDownRecordDetail)
- 数据来源标注

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 每层独立 skeleton
- **Empty (no data):** 空状态插画 + "该层级暂无数据"
- **Empty (L4 明细):** 空表格 + "当前筛选条件下无交易记录"
- **Error:** 每层独立错误提示 + 重试按钮 (不丢失面包屑)
- **Edge:** 深链接直达 L4 — 自动递归加载 L1→L2→L3 面包屑
- **Edge:** 刷新页面保留当前层级 (路由参数持久)
- **Edge:** 浏览器前进/后退正确 (Vue Router 原生支持)

### 5. 响应式行为

| 设备 | L1 KPI | L2 表格 | L3 图表 | L4 表格 |
|------|--------|---------|---------|---------|
| web | 4 列网格 | 完整表格 | 并排图表 | 完整表格+操作列 |
| tablet | 2 列网格 | 表格水平滚动 | 堆叠图表 | 表格折叠操作列 |
| mobile | 2 列 + 钻取禁用 | 钻取置灰提示 | 仅 KPI 展示 | 无法访问 (Dialog) |

### 6. 测试要求

**Unit Tests (5 用例):**
1. drilldown store — fetchL1 正确解析 KPI + departments
2. breadcrumbs — 向下钻取正确追加
3. breadcrumbs — navigateUp 正确回退
4. L1 空数据状态
5. 深链接递归加载 L1→L2→L3 面包屑

**E2E Tests (5 用例):**
1. 从 L1 点击部门 → 进入 L2 → 面包屑更新
2. L4 浏览明细 → 点击行 → 详情弹窗
3. 浏览器回退按钮 → 返回上一层级
4. 直接访问 L3 URL → 正确渲染面包屑 + L3 数据
5. 空数据层级 → 空状态插画

### 7. 依赖

- AR-008 (RESTful drill API)
- FE-013 (移动端钻取禁用)
- FE-003 (InsightCard 钻取跳转)

---

## FE-007: FinancialOverview 组件改造

### 1. 组件结构

**文件路径：**
- `src/pages/FinancialOverview.vue` — 页面容器 (改造)
- `src/components/dashboard/KpiCard.vue` — KPI 卡片 (已有，增强)
- `src/components/dashboard/ChartWidget.vue` — 图表组件 (已有，增强)

**架构变化：**
改造前：单一 `GET /api/v1/dashboard` 大包
改造后：组合消费模式 (Dashboard BFF + Query API + Insights + Recommend)

### 2. API 合同

**`GET /api/v1/dashboard`** (BFF 缓存层，仅首次加载)

Response:
```typescript
interface DashboardResponse {
  code: number;
  data: {
    kpis: Array<{
      key: string; name: string; value: number; unit: string;
      change: number; change_type: 'increase' | 'decrease' | 'flat';
      data_range: { start: string; end: string; updated_at: string };
      abnormal: boolean;
    }>;
    charts: Array<{
      id: string; type: string; title: string;
      echarts_option: object;
    }>;
  };
}
```

**`POST /api/v1/query`** (筛选/刷新后使用)

**`GET /api/v1/insights`** (按需获取洞察)

### 3. 状态管理

**Pinia Store: `src/stores/dashboard.ts`**

```typescript
export const useDashboardStore = defineStore('dashboard', () => {
  const kpis = ref<KpiItem[]>([])
  const charts = ref<ChartItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const usingCache = ref(true)  // 是否使用 BFF 缓存

  const abnormalKpis = computed(() => kpis.value.filter(k => k.abnormal))

  async function fetchDashboard() { /* GET /api/v1/dashboard */ }
  async function refreshWithFilters(dsl: FilterDSL) { /* POST /api/v1/query + 绕过缓存 */ }
  function highlightChart(metrics: string[]) { /* 图表联动高亮 */ }

  return { kpis, charts, loading, error, usingCache, abnormalKpis, fetchDashboard, refreshWithFilters, highlightChart }
})
```

### 4. UI/UX 细节

**FinancialOverview 布局 (自上而下)：**

```
┌──────────────────────────────────────────┐
│  AdvancedFilter (全局筛选)                │
├──────────┬──────────┬──────────┬──────────┤
│  KPI 1   │  KPI 2   │  KPI 3   │  KPI 4   │
│  收入    │  毛利率  │  DSO     │  现金流  │
│  [时间]  │  [时间]  │  [时间]  │  [时间]  │
├──────────┴──────────┴──────────┴──────────┤
│  AIChartRecommender (折叠面板，按需展开)    │
├──────────────────────────────────────────┤
│  InsightList (横向滚动 / 列表)             │
├──────────────────────────────────────────┤
│  ChartWidget (收入趋势 折线图)             │
├──────────────────────────────────────────┤
│  ChartWidget × N (其他图表 grid 布局)      │
└──────────────────────────────────────────┘
```

**KPI 卡片新增：**
- 显示数据时间范围 (PM-012, "2025年1月 — 2025年12月，更新于 14:32")
- 异常 KPI 红色角标
- 钻取图标 (移动端置灰)

**图表联动 (InsightCard → ChartWidget)：**
1. 用户点击 InsightCard 中的指标
2. emit chart-link metrics
3. ChartWidget 接收 linkMetrics prop
4. ECharts 调用 `chart.dispatchAction({ type: 'highlight', seriesIndex: ... })`
5. 联动取消：点击图表空白区域

**Loading/Empty/Error/Edge Cases:**
- **Loading:** KPI 骨架屏 + 图表骨架 + "加载中..." 文字
- **Empty (no data):** "暂无数据，请检查数据源"
- **Error:** 区分 BFF 缓存 vs Query API 错误
- **Edge:** BFF 缓存命中失败时降级为 Query API
- **Edge:** KPI 数值过大时自动格式化 (万/亿单位)

### 5. 响应式行为

| 设备 | KPI 网格 | 图表网格 | Insight 区 |
|------|---------|---------|-----------|
| web | 4 列 (fixed 280px each) | 3 列 grid | 右侧面板 |
| tablet | 2 列 x 2 行 | 2 列 grid | 底部面板 |
| mobile | 2 列 x 2 行，缩小字体 | 1 列 | 横向滑动卡片 |

### 6. 测试要求

**Unit Tests (4 用例):**
1. dashboard store — fetchDashboard 正确解析 KPI + charts
2. dashboard store — refreshWithFilters 绕过 BFF 调用 query API
3. abnormalKpis computed 正确过滤
4. KPI 数值格式化 (万/亿)

**E2E Tests (3 用例):**
1. 首次加载 → BFF 缓存渲染 → KPI + 图表展示
2. 修改筛选条件 → 调用 query API → 图表更新
3. 点击 InsightCard 指标 → 图表高亮对应区域

### 7. 依赖

- FE-002 (AIChartRecommender 集成)
- FE-003 (InsightCard 集成)
- FE-004 (AdvancedFilter 集成)
- FE-012 (KPI 数据新鲜度)
- AR-007 (双数据路径策略)

---

## FE-008/009/010: ReportCenter (合并实现)

### 1. 组件结构

**文件路径：**
- `src/pages/ReportCenter.vue` — 页面容器
- `src/components/report/ReportTaskList.vue` — 任务列表 + 状态 Tab
- `src/components/report/ReportTaskCard.vue` — 单条任务卡片
- `src/components/report/ReportStepProgress.vue` — 4 步进度指示器
- `src/components/report/ReportCreateModal.vue` — 新建报告弹窗
- `src/components/report/ReportPreviewModal.vue` — 报告预览/下载弹窗
- `src/composables/useReportTask.ts` — 任务列表 + 轮询 + 取消重试

### 2. API 合同

**`POST /api/v1/reports`** — 创建报告任务

Request:
```typescript
interface CreateReportRequest {
  report_type: 'daily' | 'weekly' | 'monthly';
  date_range: { start: string; end: string };
  sections?: string[];  // 报告章节，不传则全部
}
```

Response (200):
```typescript
interface CreateReportResponse {
  code: number;
  data: {
    id: string;
    status: 'pending';
    created_at: string;
  };
}
```

**`GET /api/v1/reports?status=running&page=1&page_size=20`**

Response (200):
```typescript
interface ReportListResponse {
  code: number;
  data: {
    items: ReportTask[];
    total: number;
    page: number;
    page_size: number;
  };
}

interface ReportTask {
  id: string;
  name: string;
  report_type: 'daily' | 'weekly' | 'monthly';
  date_range: { start: string; end: string };
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'cancelling';
  current_step: 'collecting_data' | 'ai_analysis' | 'document_generating' | 'completed' | 'failed';
  step_started_at: string | null;
  progress: number;  // 0-100, 可选, 步骤内部进度
  retry_count: number;
  parent_task_id: string | null;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  file_size?: number;  // completed 后有
}
```

**`POST /api/v1/reports/{id}/cancel`**

Response (200):
```typescript
{ code: 0, data: { status: 'cancelling' } }
```

最大等待 30s，超时后 `GET /api/v1/reports/{id}` 返回 `status` 确认。

**`POST /api/v1/reports/{id}/retry`**

保留原始参数，新任务 `parent_task_id` 指向当前任务。

**`GET /api/v1/reports/{id}/download?format=docx`**

Response: Binary file stream (Content-Disposition: attachment)

### 3. 状态管理

**Pinia Store: `src/stores/report.ts`**

```typescript
export const useReportStore = defineStore('report', () => {
  const tasks = ref<ReportTask[]>([])
  const total = ref(0)
  const loading = ref(false)
  const activeTab = ref<string>('all')  // all | running | completed | failed
  const pollingInterval = ref<number | null>(null)
  const creating = ref(false)

  const hasRunningTasks = computed(() => tasks.value.some(t => t.status === 'running' || t.status === 'pending'))
  const runningCount = computed(() => tasks.value.filter(t => t.status === 'running' || t.status === 'pending').length)

  async function fetchTasks(params?: { status?: string; page?: number }) { /* GET /api/v1/reports */ }
  async function createReport(req: CreateReportRequest) { /* POST /api/v1/reports */ }
  async function cancelTask(id: string) { /* POST /api/v1/reports/{id}/cancel */ }
  async function retryTask(id: string) { /* POST /api/v1/reports/{id}/retry */ }
  async function downloadReport(id: string, format: 'docx' | 'pdf') { /* binary download */ }

  function startPolling() {
    // running 时 5s, 其他 10s
    pollingInterval.value = window.setInterval(async () => {
      await fetchTasks()
      if (runningCount.value === 0) stopPolling()
    }, hasRunningTasks.value ? 5000 : 10000)
  }
  function stopPolling() {
    if (pollingInterval.value) { clearInterval(pollingInterval.value); pollingInterval.value = null }
  }

  return { tasks, total, loading, activeTab, creating, hasRunningTasks, runningCount,
    fetchTasks, createReport, cancelTask, retryTask, downloadReport, startPolling, stopPolling }
})
```

### 4. UI/UX 细节

**ReportTaskCard 布局：**
```
┌─────────────────────────────────────────────────┐
│ [状态徽章] 报告名称          类型    创建时间    │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│ │数据收集│ │AI分析│ │文档生成│ │完成  │           │
│ └──────┘ └──────┘ └──────┘ └──────┘           │
│ 步骤停留 > 5min: "此步骤耗时较长，请耐心等待"    │
│ [取消] [重试] [下载]                            │
└─────────────────────────────────────────────────┘
```

**状态徽章 (Badge) 颜色：**
| 状态 | 颜色 | 图标 |
|------|------|------|
| pending | #d9d9d9 (灰色) | ClockCircleOutlined |
| running | #1890ff (蓝色) | LoadingOutlined (旋转) |
| completed | #52c41a (绿色) | CheckCircleOutlined |
| failed | #ff4d4f (红色) | CloseCircleOutlined |
| cancelled | #faad14 (黄色) | MinusCircleOutlined |
| cancelling | #faad14 (黄色, 闪烁) | LoadingOutlined (旋转) |

**4 步进度指示器 (ReportStepProgress)：**
```typescript
interface StepProgressProps {
  currentStep: ReportTask['current_step'];
  status: ReportTask['status'];
  stepStartedAt: string | null;
}
```
- 步骤：数据收集 → AI分析 → 文档生成 → 完成
- 状态图标：灰色圆点 (pending) / 蓝色旋转 (active) / 绿色勾 (done) / 红色叉 (failed)
- 不显示百分比
- 当前步骤停留 > 5 分钟时显示 "此步骤耗时较长，请耐心等待" (定时器检测)

**取消逻辑：**
- pending 状态：显示取消按钮 → 点击直接取消
- running 状态：显示取消按钮 → 状态变为 cancelling (黄色闪烁)
- 轮询检测确认：最多等待 30s
- 超时未确认 → 标记为 "取消失败" (恢复原状态)
- completed/failed/cancelled 不显示取消按钮

**重试逻辑：**
- failed 状态显示重试按钮
- retry_count >= 3 时置灰，显示 "已连续失败 3 次，请联系管理员"
- 点击重试创建新任务 (保留原参数)
- 原任务保留不变，新任务 parent_task_id 指向原任务

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 列表骨架屏，5 行灰色条
- **Empty:** "暂无报告任务，点击"新建报告"开始"
- **Empty (filtered):** "没有符合条件的任务"
- **Error (fetch):** "任务列表加载失败" + 重试按钮
- **Error (create):** 弹窗显示错误信息
- **Error (cancel):** "取消失败，请稍后重试"
- **Edge:** 批量同时在跑的超过 3 个时提示 "已有大量任务在运行，可能影响性能"
- **Edge:** 浏览器 Tab 切换后恢复轮询 (visibilitychange 事件)
- **Edge:** 下载大文件时显示进度条 (axios onDownloadProgress)

### 5. 响应式行为

| 设备 | 任务列表 | 步骤指示器 |
|------|---------|-----------|
| web | 表格列表 (多列) | 水平 4 步条 |
| tablet | 卡片列表 (2 列) | 水平 4 步条 (略小) |
| mobile | 单列卡片列表 | 垂直 4 步条 (步骤说明在上方) |

### 6. 测试要求

**Unit Tests (8 用例):**
1. report store — fetchTasks 正确解析列表
2. report store — createReport 创建任务
3. report store — cancelTask pending 状态取消
4. report store — retryTask 保留原始参数
5. report store — startPolling running 时 5s 间隔
6. report store — hasRunningTasks computed 正确
7. step progress — 步骤状态映射正确
8. retry_count >= 3 时 disabled

**E2E Tests (5 用例):**
1. 创建报告 → 任务列表出现 pending → 转为 running → completed
2. pending 任务点击取消 → 状态变 cancelled
3. failed 任务点击重试 → 创建新任务
4. completed 任务点击下载 → 触发文件下载
5. 状态 Tab 筛选 (全部/进行中/已完成/失败)

### 7. 依赖

- PM-006 (步骤进度指示器需求)
- PM-007 (任务列表需求)
- PM-008 (取消功能需求)
- PM-009 (重试功能需求)
- AR-010 (报告异步任务架构)
- FE-011 (通知铃铛联动)

---

## FE-011: TopBar 通知铃铛

### 1. 组件结构

**文件路径：**
- `src/components/layout/TopBar.vue` — TopBar 主组件 (已有，增强)
- `src/components/layout/NotificationBell.vue` — 通知铃铛组件
- `src/composables/useNotifications.ts` — 通知逻辑

### 2. API 合同

**`GET /api/v1/notifications?page=1&limit=20`**

Response (200):
```typescript
interface NotificationResponse {
  code: number;
  data: {
    items: NotificationItem[];
    total: number;
    unread_count: number;
  };
}

interface NotificationItem {
  id: string;
  type: 'report_completed' | 'report_failed' | 'data_sync' | 'system';
  title: string;
  content: string;
  is_read: boolean;
  related_resource_id?: string;  // 关联的报告 ID
  created_at: string;
}
```

**`POST /api/v1/notifications/{id}/read`** — 单条标记已读

Response (200):
```typescript
{ code: 0, data: null }
```

### 3. 状态管理

**Pinia Store: 在 `src/stores/notification.ts`**

```typescript
export const useNotificationStore = defineStore('notification', () => {
  const items = ref<NotificationItem[]>([])
  const unreadCount = ref(0)
  const total = ref(0)
  const loading = ref(false)
  const dropdownVisible = ref(false)

  async function fetchNotifications() { /* GET /api/v1/notifications */ }
  async function markAsRead(id: string) { /* POST /api/v1/notifications/{id}/read */ }
  async function markAllAsRead() { /* 循环标记 */ }

  return { items, unreadCount, total, loading, dropdownVisible, fetchNotifications, markAsRead, markAllAsRead }
})
```

### 4. UI/UX 细节

**NotificationBell.vue Props:**
```typescript
interface NotificationBellProps {
  unreadCount: number;
}
```

**Events:**
```typescript
interface NotificationBellEmits {
  (e: 'mark-read', id: string): void
  (e: 'navigate', resourceId: string): void  // 跳转 ReportCenter
}
```

**交互：**
1. 铃铛 icon 带红色 Badge (unreadCount > 0)
2. 点击展开下拉列表 (最多 20 条，按时间倒序)
3. 每条通知显示：icon (按 type) + 标题 + 时间
4. 未读通知灰色背景，点击即标记已读
5. 报告完成通知点击跳转 ReportCenter 对应任务
6. 底部 "查看全部" → 跳转 ReportCenter 页面
7. 通知列表轮询：60s 间隔 (低频)

**通知类型 Icon：**
| type | Icon | Color |
|------|------|-------|
| report_completed | FileDoneOutlined | #52c41a |
| report_failed | CloseCircleOutlined | #ff4d4f |
| data_sync | SyncOutlined | #1890ff |
| system | InfoCircleOutlined | #faad14 |

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 下拉列表中 3 行骨架
- **Empty:** "暂无通知"
- **Error:** 下拉列表显示 "加载失败"
- **Edge:** 通知超过 99 条时 Badge 显示 "99+"
- **Edge:** 批量标记已读 (markAllAsRead)

### 5. 响应式行为

| 设备 | 铃铛位置 | 下拉列表 |
|------|---------|---------|
| web | TopBar 右端 | 固定下拉 (360px) |
| tablet | TopBar 右端 | 同 web |
| mobile | TopBar 右端 | 底部 sheet (全宽) |

### 6. 测试要求

**Unit Tests (3 用例):**
1. notification store — fetchNotifications 解析 unread_count
2. notification store — markAsRead 本地更新 is_read
3. 通知类型 icon 映射正确

**E2E Tests (2 用例):**
1. 收到通知 → 铃铛显示红点 → 展开列表
2. 点击未读通知 → 标记已读 → 红点减少

### 7. 依赖

- FE-008 (ReportCenter 联动)
- PM-005 (通知框架)

---

## FE-012: 数据新鲜度指示器

### 1. 组件结构

**文件路径：**
- `src/components/layout/DataFreshnessIndicator.vue` — TopBar 新鲜度指示器
- `src/components/dashboard/KpiFreshnessBadge.vue` — KPI 卡片时效性 Badge
- `src/composables/useDataFreshness.ts` — 新鲜度逻辑

### 2. API 合同

**`GET /api/v1/system/data-freshness`**

Response (200):
```typescript
interface DataFreshnessResponse {
  code: number;
  data: {
    last_sync_time: string;      // ISO 8601
    data_range: {
      start: string;              // "2025-01-01"
      end: string;                // "2025-12-31"
    };
    status: 'fresh' | 'stale' | 'error';
    next_sync_at: string | null;  // ISO 8601
  };
}
```

**`POST /api/v1/data-sync/refresh`** — 手动刷新

Response (200):
```typescript
{ code: 0, data: { sync_id: string; status: 'triggered' } }
```

### 3. 状态管理

**Pinia Store: `src/stores/freshness.ts`**

```typescript
export const useFreshnessStore = defineStore('freshness', () => {
  const freshness = ref<DataFreshnessResponse['data'] | null>(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const lastManualRefresh = ref<number>(0)  // timestamp
  const cooldownSeconds = 60

  const timeAgo = computed(() => {
    if (!freshness.value) return ''
    const diff = Date.now() - new Date(freshness.value.last_sync_time).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return '刚刚'
    return `${mins} 分钟前`
  })

  const canRefresh = computed(() => Date.now() - lastManualRefresh.value > cooldownSeconds * 1000)
  const cooldownRemaining = computed(() => Math.max(0, cooldownSeconds - Math.floor((Date.now() - lastManualRefresh.value) / 1000)))

  async function fetchFreshness() { /* 每 60s 轮询 */ }
  async function triggerRefresh() {
    if (!canRefresh.value) return
    refreshing.value = true
    await axios.post('/api/v1/data-sync/refresh')
    lastManualRefresh.value = Date.now()
    refreshing.value = false
  }

  return { freshness, loading, refreshing, timeAgo, canRefresh, cooldownRemaining, fetchFreshness, triggerRefresh }
})
```

### 4. UI/UX 细节

**DataFreshnessIndicator.vue：**

TopBar 中显示：
```
[SyncOutlined] 数据更新于 14:32  |  [ReloadOutlined]  (cooldown)
```

| status | 文字颜色 | 说明 |
|--------|---------|------|
| fresh | #8c8c8c (灰色) | ≤30min |
| stale | #faad14 (黄色) | >30min |
| error | #ff4d4f (红色) | >60min 或同步失败 |

手动刷新按钮：
- 点击触发 `POST /api/v1/data-sync/refresh`
- 按钮 60s cooldown，倒计时显示
- cooldown 期间按钮 disabled + 显示剩余秒数

**KpiFreshnessBadge (KPI 卡片下方)：**
- 小字显示 "2025年1月 — 2025年12月，更新于 14:32"

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 显示 "--:--"
- **Error (API):** TopBar 指示器显示 "数据新鲜度未知"，红色警告
- **Edge:** 浏览器 Tab 隐藏时暂停轮询 (Page Visibility API)
- **Edge:** 手动刷新后 3s 内自动重新获取 freshness

### 5. 响应式行为

| 设备 | 位置 | 形态 |
|------|------|------|
| web | TopBar 右上，KPI 卡片下方 | 完整文字 |
| tablet | TopBar 右上 | 缩短 "更新于 HH:MM" |
| mobile | TopBar 右上 | 仅显示颜色圆点 + 时间 |

### 6. 测试要求

**Unit Tests (3 用例):**
1. freshness store — fetchFreshness 正确解析 status
2. canRefresh computed — 60s cooldown 逻辑
3. timeAgo computed — 正确计算时间差

**E2E Tests (2 用例):**
1. 页面加载 → TopBar 显示 "数据更新于 HH:MM"
2. 点击手动刷新 → 按钮 cooldown → 60s 后恢复

### 7. 依赖

- FE-007 (KPI 卡片集成)
- PM-012 (数据新鲜度需求)

---

## FE-013: Mobile 钻取禁用

### 1. 组件结构

**文件路径：**
- `src/composables/useDrillDownGuard.ts` — 钻取禁用检测逻辑
- `src/components/common/DrillDownGuard.vue` — 包裹组件，检测钻取入口
- `src/pages/drilldown/DrillDownContainer.vue` — 路由容器 (增强)

**不需要新建大量组件，以 composable + 指令为主。**

### 2. API 合同

不涉及独立 API。依赖 `window.innerWidth` / `window.matchMedia('(max-width: 767px)')` 检测。

### 3. 状态管理

不涉及独立 Store。逻辑封装在 `useDrillDownGuard.ts`：

```typescript
// src/composables/useDrillDownGuard.ts
import { ref, computed, onMounted, onUnmounted } from 'vue'

export function useDrillDownGuard() {
  const isMobile = ref(false)
  const guardMessage = '钻取功能请在桌面端使用'

  const checkMobile = () => { isMobile.value = window.innerWidth < 768 }
  const mediaQuery = window.matchMedia('(max-width: 767px)')

  onMounted(() => {
    checkMobile()
    mediaQuery.addEventListener('change', checkMobile)
  })
  onUnmounted(() => mediaQuery.removeEventListener('change', checkMobile))

  return { isMobile, guardMessage }
}
```

### 4. UI/UX 细节

**钻取入口检测：**
在以下钻取入口包裹 `DrillDownGuard` 或调用 `useDrillDownGuard`：
- KPI 卡片上的钻取 icon
- InsightCard "查看详情" 按钮
- 表格中的可点击行 (L1 部门行)
- 图表中的钻取点击事件

**触发表现：**
- **入口按钮：** 移动端直接置灰 (opacity: 0.5; cursor: not-allowed)
- **点击/触摸置灰按钮：** Toast 提示 "钻取功能请在桌面端使用" (duration: 3s)
- **直接访问钻取 URL：** DrillDownContainer 检测移动端 → 弹出 Modal Dialog
  - Dialog 文字："钻取功能请在桌面端使用"
  - 按钮："返回仪表盘" → router.push('/')
  - 不渲染任何钻取内容
  - 保留 KPI 卡片和图表浏览能力

**DrillDownGuard.vue:** (可选，用于指令式包裹)
```typescript
interface DrillDownGuardProps {
  disabled?: boolean;  // 外部可覆盖
}
// emits: (e: 'guard-triggered') => void
```

### 5. 响应式行为

仅影响 <768px 宽度的设备。web/tablet 无任何变化。

### 6. 测试要求

**Unit Tests (2 用例):**
1. useDrillDownGuard — 宽度 < 768 时 isMobile=true
2. useDrillDownGuard — 宽度变化事件监听

**E2E Tests (2 用例):**
1. 移动端视口下点击钻取按钮 → Toast 提示
2. 移动端直接访问钻取 URL → Dialog 弹出 → 点击返回

### 7. 依赖

- FE-006 (DrillDown 组件)
- PM-013 (移动端钻取禁用 decision)
- DEC-07 (决策确认)

---

## FE-014: 响应式布局验证

### 1. 测试文件结构

- `src/composables/useResponsive.ts` — 响应式工具函数
- `tests/responsive/` — 响应式测试

### 2. 技术实现

```typescript
// src/composables/useResponsive.ts
import { ref, computed, onMounted, onUnmounted } from 'vue'

export type DeviceType = 'web' | 'tablet' | 'mobile'

const BREAKPOINTS = {
  mobile: 767,    // <768
  tablet: 1023,   // 768-1023
  web: 1024,      // >=1024
}

export function useResponsive() {
  const width = ref(window.innerWidth)
  const device = computed<DeviceType>(() => {
    if (width.value < 768) return 'mobile'
    if (width.value < 1024) return 'tablet'
    return 'web'
  })
  const isMobile = computed(() => device.value === 'mobile')
  const isTablet = computed(() => device.value === 'tablet')
  const isWeb = computed(() => device.value === 'web')

  const resizeHandler = () => { width.value = window.innerWidth }

  onMounted(() => window.addEventListener('resize', resizeHandler))
  onUnmounted(() => window.removeEventListener('resize', resizeHandler))

  return { width, device, isMobile, isTablet, isWeb }
}
```

**CSS 断点 (scss/less variables):**
```scss
// src/styles/breakpoints.scss
$web-min: 1024px;
$tablet-min: 768px;
$tablet-max: 1023px;
$mobile-max: 767px;
```

### 3. 验证清单 (7 项)

| # | 验证项 | 涉及组件 | 验证方法 |
|---|--------|---------|---------|
| 1 | 侧边栏 web 展开 / tablet 折叠 / mobile 底部 Tab | Sidebar, MobileTabBar | Playwright viewport 切换 |
| 2 | 筛选器 web 顶部 / tablet 可折叠 / mobile 抽屉 | AdvancedFilter, MobileDrawer | Playwright viewport 切换 |
| 3 | 洞察卡片 web 右侧 / tablet 底部 / mobile 横向滑动 | InsightList | Playwright viewport 切换 |
| 4 | 图表网格 3 列 / 2 列 / 1 列 | ChartWidget Grid | Playwright viewport 切换 |
| 5 | KPI 卡片 4 列 / 2 列 / 2 列 | KpiCard Grid | Playwright viewport 切换 |
| 6 | 相关性矩阵 web 并排 / tablet 堆叠 / mobile 缩放 | CorrelationMatrix | Playwright viewport 切换 |
| 7 | 步骤进度 web 水平 / mobile 垂直 | ReportStepProgress | Playwright viewport 切换 |

### 4. 测试要求

**E2E Tests (7 用例):** 上述 7 项每项对应 1 个 Playwright 用例，通过 `test.use({ viewport: { width: 1920, height: 1080 } })` 切换。

### 5. 依赖

所有组件最终确定布局后执行。建议在 FE-001~FE-013 全部完成后再实施此项验证。

---

## FE-015: TransactionAnalysis (Phase 2)

### 1. 组件结构

**文件路径：**
- `src/pages/TransactionAnalysis.vue` — 页面容器
- `src/components/transaction/TransactionTabs.vue` — 维度切换 Tab
- `src/components/transaction/LargeAmountTable.vue` — 大额交易列表
- `src/components/transaction/AnomalyAlertList.vue` — 异常交易预警列表

### 2. API 合同

**`GET /api/v1/transactions/contracts`**
**`GET /api/v1/transactions/orders`**
**`GET /api/v1/transactions/projects`**
**`GET /api/v1/transactions/anomalies`**
**`GET /api/v1/transactions/large-amounts`**

### 3. 状态管理

**Pinia Store: `src/stores/transaction.ts`**

### 4. UI/UX 细节

(略 — Phase 2 详化)

### 5. 响应式行为

| 设备 | 表格 | 图表 |
|------|------|------|
| web | 完整操作列 | 并排 |
| tablet | 折叠操作 | 堆叠 |
| mobile | 水平滚动 | 单列 |

### 6. 测试要求

**Unit Tests (3 用例):**
1. transaction store — 切换 Tab 正确加载对应数据
2. 大额交易高亮逻辑
3. 异常交易标记

**E2E Tests (3 用例):**
1. Tab 切换 (合同/订单/项目)
2. 大额交易列表阈值高亮
3. 异常交易预警联动

### 7. 依赖

- FE-004 (AdvancedFilter 集成)
- FE-006 (L4 钻取基础)
- AR-002 (交易分析 API, Phase 2)

---

## FE-016: ForecastChart + ConfidenceBand

### 1. 组件结构

**文件路径：**
- `src/components/prediction/ForecastChart.vue` — 预测图表
- `src/components/prediction/ConfidenceBand.vue` — 置信区间渲染
- `src/pages/PredictionPage.vue` — 预测分析页 (已有)
- `src/composables/usePrediction.ts` — 预测逻辑 + 拒绝规则

### 2. API 合同

**`POST /api/v1/predictions`**

Request:
```typescript
interface PredictRequest {
  metric: string;               // 预测指标: 'revenue' | 'dso' | 'ar_aging' | 'cost'
  historical_data_range?: { start: string; end: string };
  forecast_months?: number;     // 默认 3
  confidence_level?: number;    // 默认 0.8
}
```

Response (200):
```typescript
interface PredictResponse {
  code: number;
  data: {
    id: string;
    metric: string;
    forecast: Array<{
      date: string;           // YYYY-MM
      predicted_value: number;
      lower_bound: number;    // 置信区间下限
      upper_bound: number;    // 置信区间上限
    }>;
    historical: Array<{
      date: string;
      actual_value: number;
    }>;
    confidence_level: number;
    model_metrics: {
      mape: number;           // 平均绝对百分比误差
      r2: number;             // R²
    };
    rejection?: {
      rejected: boolean;
      reason: string;         // 拒绝原因
    };
    generated_at: string;
  };
}
```

**`GET /api/v1/predictions/{id}`** — 获取已有预测结果

### 3. 状态管理

**Pinia Store: `src/stores/prediction.ts`**

```typescript
export const usePredictionStore = defineStore('prediction', () => {
  const prediction = ref<PredictResponse['data'] | null>(null)
  const history = ref<PredictItem[]>([])
  const loading = ref(false)
  const rejected = computed(() => prediction.value?.rejection?.rejected ?? false)
  const rejectionReason = computed(() => prediction.value?.rejection?.reason ?? '')

  const echartsOption = computed(() => {
    if (!prediction.value) return null
    // 构建包含置信区间的 ECharts option
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['实际值', '预测值', '置信区间'] },
      xAxis: { type: 'category' },
      yAxis: { type: 'value' },
      series: [
        {
          name: '置信区间',
          type: 'line',
          data: prediction.value.forecast.map(f => [f.date, f.upper_bound, f.lower_bound]),
          // 使用自定义 series 渲染区间带
        },
        {
          name: '预测值',
          type: 'line',
          data: prediction.value.forecast.map(f => [f.date, f.predicted_value]),
          lineStyle: { type: 'dashed' },
        },
        {
          name: '实际值',
          type: 'line',
          data: prediction.value.historical.map(h => [h.date, h.actual_value]),
        },
      ]
    }
  })

  async function predict(req: PredictRequest) { /* POST /api/v1/predictions */ }
  async function fetchPrediction(id: string) { /* GET /api/v1/predictions/{id} */ }

  return { prediction, history, loading, rejected, rejectionReason, echartsOption, predict, fetchPrediction }
})
```

### 4. UI/UX 细节

**ForecastChart.vue Props:**
```typescript
interface ForecastChartProps {
  metric: string;
  predictionId?: string;       // 已有预测 ID
  height?: number;              // 默认 400
}
```

**Events:**
```typescript
interface ForecastChartEmits {
  (e: 'predict', metric: string): void
}
```

**ECharts Option 模式：**
```typescript
// 置信区间带渲染 (2 种方式)
// 方式 1: 使用自定义系列 (preferred)
{
  type: 'custom',
  renderItem: (params, api) => {
    const points = []  // 上下边界多边形
    // 渲染填充区域
    return { type: 'polygon', shape: { points }, style: { fill: 'rgba(24,144,255,0.15)' } }
  },
  data: forecastData,
}

// 方式 2: 两个 line series 夹填充区域 (ECharts 5 标准做法)
{
  // 上边界线 (透明)
  // 下边界线 (透明)
  // 中间填充区域
  type: 'line',
  areaStyle: { color: 'rgba(24,144,255,0.15)' },
  lineStyle: { opacity: 0 },
  data: upperBounds,
}
```

**拒绝规则 UI：**
当 `rejection.rejected === true` 时：
1. 图表区域显示覆盖层
2. 显示拒绝原因卡片：`[WarningOutlined] 预测不可用: ${reason}`
3. 提供 "了解详情" 链接 (展开技术原因)
4. 降级：显示历史数据趋势线 (无预测部分)
5. 提供 "联系管理员" 按钮 (可选)

**技术指标展示：**
- 模型指标卡片 (折叠)
  - MAPE (Mean Absolute Percentage Error)
  - R² (拟合优度)
  - 置信区间说明

**Loading/Empty/Error/Edge Cases:**
- **Loading:** 图表区域骨架屏 + "AI 正在分析数据趋势..."
- **Empty (no history):** "历史数据不足，无法进行预测 (至少需要 12 个月数据)"
- **Error:** "预测服务暂时不可用" + 降级展示纯历史数据
- **Edge:** 置信区间过宽 (> ±50%) 时警告 "预测不确定性较高"
- **Edge:** 选择未来月份超过 6 时提示 "长期预测准确度可能下降"

### 5. 响应式行为

| 设备 | 图表 | 指标卡片 |
|------|------|---------|
| web | 全宽 800px+ | 右侧栏 |
| tablet | 全宽 | 图表下方 |
| mobile | 全宽, 可缩放(touch) | 图表下方折叠 |

### 6. 测试要求

**Unit Tests (5 用例):**
1. prediction store — predict 正确解析 forecast + bounds
2. echartsOption computed — 正确构建置信区间 option
3. rejected computed — 拒绝时正确返回 true
4. 置信区间过宽时警告逻辑
5. 历史数据不足时错误提示

**E2E Tests (3 用例):**
1. 选择指标 → 点击预测 → 展示预测曲线 + 置信区间
2. 预测被拒绝 → 显示拒绝原因卡片 + 历史趋势降级
3. 切换预测指标 → 图表重新渲染

### 7. 依赖

- AR-002 (predict API, 已升 P0)
- PM-003 (预测升 P0)

---

## FE-017: DataSourceList / DataQualityDashboard / ExcelUploader (Phase 3)

### 1. 组件结构

**文件路径：**
- `src/pages/DataManagement.vue` — 数据管理页容器
- `src/components/data/DataSourceList.vue` — 数据源列表 CRUD
- `src/components/data/DataQualityDashboard.vue` — 数据质量仪表板
- `src/components/data/ExcelUploader.vue` — Excel 上传组件

### 2. API 合同

**数据源 CRUD:** `GET/POST/PUT/DELETE /api/v1/data-sources`
**质量统计:** `GET /api/v1/data-quality/summary`
**错误日志:** `GET /api/v1/data-quality/errors?page=1&page_size=20`
**上传:** `POST /api/v1/uploads/excel` (multipart/form-data, max 10MB)

### 3. 状态管理

**Pinia Store: `src/stores/dataManagement.ts`**

### 4. UI/UX 细节

(略 — Phase 3 详化。关键约束：上传文件限制 10MB，仅 .xlsx/.xls 类型)

### 5. 测试要求

**Unit Tests (4 用例):**
1. DataSourceList — CRUD 操作
2. DataQualityDashboard — 质量指标渲染
3. ExcelUploader — 文件类型校验
4. ExcelUploader — 文件大小校验 (10MB 限制)

**E2E Tests (4 用例):**
1. 数据源列表 CRUD
2. 质量仪表板统计展示
3. 上传有效 Excel
4. 上传超大文件 → 413 错误

### 6. 依赖

- AR-003 (数据源/质量/上传 API, Phase 3)

---

## 项目文件结构总览 (Phase 1)

```
src/
├── App.vue
├── main.ts
├── router/
│   └── index.ts                        # 路由定义 + 导航守卫
├── stores/
│   ├── auth.ts                         # FE-001 认证/权限
│   ├── recommend.ts                    # FE-002 图表推荐
│   ├── insights.ts                     # FE-003 洞察
│   ├── filter.ts                       # FE-004 筛选
│   ├── correlation.ts                  # FE-005 相关性分析
│   ├── drilldown.ts                    # FE-006 钻取
│   ├── dashboard.ts                    # FE-007 仪表板
│   ├── report.ts                       # FE-008/009/010 报告中心
│   ├── notification.ts                 # FE-011 通知
│   ├── freshness.ts                    # FE-012 数据新鲜度
│   ├── prediction.ts                   # FE-016 预测
│   └── transaction.ts                  # FE-015 (Phase 2)
├── composables/
│   ├── usePermission.ts                # FE-001 权限
│   ├── useChartRecommend.ts            # FE-002 推荐逻辑
│   ├── useInsights.ts                  # FE-003 洞察
│   ├── useFilter.ts                    # FE-004 筛选 DSL
│   ├── useCorrelation.ts               # FE-005 相关性
│   ├── useDrillDown.ts                 # FE-006 钻取
│   ├── useReportTask.ts                # FE-008/009/010 报告
│   ├── useNotifications.ts             # FE-011 通知
│   ├── useDataFreshness.ts             # FE-012 新鲜度
│   ├── useDrillDownGuard.ts            # FE-013 钻取守卫
│   ├── useResponsive.ts                # FE-014 响应式
│   ├── usePrediction.ts                # FE-016 预测
│   └── useAxios.ts                     # 全局 axios 配置
├── components/
│   ├── layout/
│   │   ├── Sidebar.vue                 # FE-001
│   │   ├── SidebarItem.vue             # FE-001
│   │   ├── TopBar.vue                  # FE-011, FE-012
│   │   ├── NotificationBell.vue        # FE-011
│   │   ├── DataFreshnessIndicator.vue  # FE-012
│   │   └── MobileTabBar.vue            # FE-001 移动端
│   ├── ai/
│   │   ├── AIChartRecommender.vue      # FE-002
│   │   ├── RecommenderCard.vue          # FE-002
│   │   ├── RecommendationCarousel.vue   # FE-002
│   │   ├── InsightCard.vue             # FE-003
│   │   └── InsightList.vue             # FE-003
│   ├── filter/
│   │   ├── AdvancedFilter.vue          # FE-004
│   │   ├── FilterRow.vue               # FE-004
│   │   ├── FilterViewSaveModal.vue     # FE-004
│   │   └── FilterViewList.vue          # FE-004
│   ├── correlation/
│   │   ├── CorrelationMatrix.vue       # FE-005
│   │   ├── CorrelationDetail.vue       # FE-005
│   │   └── CalibrationPanel.vue        # FE-005
│   ├── dashboard/
│   │   ├── KpiCard.vue                 # FE-007 (增强)
│   │   ├── KpiFreshnessBadge.vue       # FE-012
│   │   └── ChartWidget.vue             # FE-007 (增强)
│   ├── report/
│   │   ├── ReportTaskList.vue          # FE-008
│   │   ├── ReportTaskCard.vue          # FE-008
│   │   ├── ReportStepProgress.vue      # FE-009
│   │   ├── ReportCreateModal.vue       # FE-008
│   │   └── ReportPreviewModal.vue      # FE-008
│   ├── prediction/
│   │   ├── ForecastChart.vue           # FE-016
│   │   └── ConfidenceBand.vue          # FE-016
│   ├── transaction/                    # Phase 2
│   │   ├── TransactionTabs.vue
│   │   ├── LargeAmountTable.vue
│   │   └── AnomalyAlertList.vue
│   └── common/
│       └── DrillDownGuard.vue          # FE-013
├── pages/
│   ├── FinancialOverview.vue           # FE-007 (改造)
│   ├── CorrelationAnalysis.vue         # FE-005
│   ├── ReportCenter.vue                # FE-008/009/010
│   ├── PredictionPage.vue              # FE-016 (增强)
│   ├── TransactionAnalysis.vue         # FE-015 (Phase 2)
│   ├── DataManagement.vue              # FE-017 (Phase 3)
│   └── drilldown/
│       ├── DrillDownContainer.vue      # FE-006
│       ├── DrillDownL1Summary.vue      # FE-006
│       ├── DrillDownL2Department.vue   # FE-006
│       ├── DrillDownL3Product.vue      # FE-006
│       ├── DrillDownL4Detail.vue       # FE-006
│       └── DrillDownRecordDetail.vue   # FE-006
├── types/                              # TypeScript 类型定义
│   ├── auth.ts
│   ├── dashboard.ts
│   ├── insights.ts
│   ├── filter.ts
│   ├── correlation.ts
│   ├── drilldown.ts
│   ├── report.ts
│   ├── notification.ts
│   ├── prediction.ts
│   └── transaction.ts
└── styles/
    ├── variables.scss
    ├── breakpoints.scss                # FE-014
    └── responsive-mixins.scss
```

---

## 实施建议与总体策略

### Phase 1 实施顺序

| 轮次 | 并行 | 任务 | 交付物 |
|------|------|------|--------|
| 轮次 1 | 基础设施 | FE-001 (Sidebar/认证) + FE-014 (响应式 composable) | 登录/路由/导航框架 |
| 轮次 2 | 数据层 | FE-004 (AdvancedFilter) + FE-012 (Freshness) | 数据查询 + 状态显示 |
| 轮次 3 | 核心页面 | FE-007 (FinancialOverview) + FE-002 (AIChartRecommender) + FE-003 (InsightCard) | 首页 + AI 推荐 + 洞察 |
| 轮次 4 | 分析能力 | FE-005 (Correlation) + FE-006 (DrillDown) + FE-016 (Forecast) | 关联分析 + 钻取 + 预测 |
| 轮次 5 | 报告中心 | FE-008/009/010 (ReportCenter) + FE-011 (Notification) | 报告生成 + 通知 |
| 轮次 6 | 收尾 | FE-013 (Mobile 钻取禁用) + FE-014 (响应式验证) | 移动端 + 全量验证 |

### 关键设计原则

1. **双数据路径**：所有组件优先走 `POST /api/v1/query`，仅 FinancialOverview 首次加载走 `GET /api/v1/dashboard` BFF
2. **乐观更新**：状态变更操作 (标记已读/校准) 先更新本地状态再发 API，失败时回滚
3. **降级策略**：AI 能力 (推荐/洞察/预测) 失败时有明确的降级路径
4. **轮询管理**：所有轮询 (报告任务/通知/数据新鲜度) 使用 `visibilitychange` 事件，Tab 隐藏时暂停
5. **错误分层**：组件级错误 (独立 retry) vs 页面级错误 (全局 error boundary)
6. **TypeScript First**：每个 API 响应定义完整 TypeScript 类型，前后端契约通过 `types/` 目录锁定

### 测试策略

| 测试类型 | 工具 | 范围 | 目标 |
|---------|------|------|------|
| Unit | Vitest | Pinia stores, composables, 工具函数 | 28 用例 |
| E2E | Playwright | 组件交互, 路由, 响应式 | 47 用例 |
| 响应式 | Playwright | viewport 切换 7 项 | 7 用例 |
| 权限 | Playwright | admin/analyst/viewer 矩阵 | 6 用例 |

### 与环境变量相关的配置 (前端)

```env
# .env (前端侧仅包含公开配置)
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_DASHBOARD_CACHE_TTL=300
VITE_POLLING_INTERVAL_DEFAULT=10000
VITE_POLLING_INTERVAL_FAST=5000
VITE_FRESHNESS_POLLING_INTERVAL=60000
VITE_UPLOAD_MAX_SIZE=10485760      # 10MB
VITE_DRILLDOWN_MOBILE_DISABLED=true
```
