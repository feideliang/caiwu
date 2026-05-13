# AI+BI 数智化财务管报系统 — 整改计划

## Context

Phase 2+3 蜂群开发完成后，前后端 API 契约严重不匹配，导致 Dashboard 页面 KPI 全为0、图表无数据、Insights/Notifications 等多个组件显示异常或崩溃。前端 build 0错误，但运行时 API 响应结构和前端期望类型完全对不上。

---

## 一、已发现 API 契约不匹配清单

### P0 — 页面崩溃 / 无数据显示

**1. Dashboard BFF — KPI缺失 + 图表字段不匹配**
- 后端返回 `{ dashboard_id, dashboard_name, device_type, charts: ChartDataItem[], layout }`（无 KPI）
- 前端期望 `{ kpis: KpiData, charts: ChartData[], updated_at }`
- 图表字段：后端 `chart_id/chart_name/chart_type/config` vs 前端 `id/title/type/data/options`
- **4个KPI卡片永远显示0，图表无数据**

**2. Notifications — 返回类型错误**
- 后端返回 `{ items, total, unread_count, page, page_size, total_pages }`
- 前端 `notificationStore` 直接 `data.data as Notification[]`，实际是对象
- `unreadCount` 计算失败 → TopBar badge 计数错误

**3. Insights — 缺少 description/severity/confidence 字段**
- 后端返回 `{ id, title, insight_type, content, created_at }`
- 前端 `Insight` 类型需要 `description, severity, confidence, related_metric`
- 卡片渲染 `insight.description` → undefined，severity 颜色异常

### P1 — 功能失效

**4. Filter Options — 缺 dimension 参数 + 响应格式不匹配**
- 前端调用无参数 → 后端 422（dimension 必填）
- 响应 `{ dimension, options[], total }` vs 前端期望 `{ fields: FilterFieldConfig[] }`

**5. Filter View Delete — HTTP 方法错误**
- 前端 `POST /filter-views/${id}/delete` → 后端 `DELETE /filter-views/{view_id}`

**6. AI Chart Recommend — 请求字段完全不匹配**
- 前端发 `{ data_type, data_sample, device }` → 后端要 `{ data_description, analysis_goal, top_k }`

**7. Correlation Analyze — 字段不匹配**
- 前端发 `{ variables: string[], date_from, date_to }` → 后端要 `{ metric_a, metric_b, method, period_start, period_end }`
- 响应：后端 `metric_a/metric_b` vs 前端期望 `variable_x/variable_y`

### P2 — 细节不匹配

**8. Filter View Save — 字段名不一致**
- 前端发 `{ name, conditions, logic }` → 后端期望 `{ name, dashboard_id, filters, is_public }`

**9. Login 响应 — User 类型字段不全**
- 后端返回 `{ id, username, email, role, is_active }` → 前端类型还有 `department, created_at, last_login`

**10. Auth Store — logout 调用不存在的方法**
- `authStore.logout()` 调用 `apiLogout()` 但 `api/auth.ts` 未导出此方法

---

## 二、历史整改要点（整合）

### 相距深远的主要原因

1. **计划先于契约固化，开发按局部理解推进。** 部分实现采用局部命名（如 `/ai/recommend/chart`），未回收成统一规范。
2. **缺少"契约为单一事实源"。** 前端 API 封装、后端路由、Pydantic schema、测试用例之间没有统一 OpenAPI/契约测试作为硬门禁。
3. **任务被按页面/模块拆开，而不是按端到端业务闭环拆开。** 很多模块存在，但从完整链路看仍有断点。
4. **UI 没有按后台作业流设计。** 管理端只实现静态入口，缺少配置→测试→触发→反馈→重试的完整闭环。
5. **邮件同步被当成后台定时任务，没有产品化。** 没有手动触发 API、同步记录表、前端按钮、进度反馈。
6. **占位实现没有被纳入技术债清单。** placeholder/mock 让页面能跑，但没有后续强制替换。
7. **测试目标从数量计划变成了局部覆盖。** 计划中 259+ 测试矩阵还要求契约、前端交互、E2E 等。

### 整改原则

- **先收敛契约，再改代码。** 不继续新增功能，先把路径、字段、状态、错误码、分页、权限统一。
- **按端到端闭环验收。** 每批整改必须从前端页面触发到后端、数据库、响应、错误处理、测试全部闭环。
- **先补 UI 操作闭环，再扩功能。** 当前优先级不是堆 API，而是让已有 API/任务在后台可配置、可触发、可观察、可重试。
- **保留已完成代码，做最小兼容整改。** 不大拆重写，优先加兼容路由、修前端封装、补 schema。
- **清理占位必须显式排期。** placeholder/mock 只能作为降级策略存在，不能伪装成业务完成。

---

## 三、整改计划

### 任务 1：API 契约修复（P0 优先）

#### P0 修复清单

| # | 文件 | 修复内容 |
|---|------|---------|
| 1 | `backend/app/schemas/query.py` | `DashboardBFFResponse` 补 `kpis` 字段；`ChartDataItem` 字段对齐前端 |
| 2 | `backend/app/api/dashboard.py` | 补充 KPI 真实数据计算（从 financial_data 表聚合） |
| 3 | `backend/app/api/insights.py` | 补 `description/severity/confidence/related_metric` 字段 |
| 4 | `backend/app/schemas/insights.py` | 更新 `InsightResponse` schema 补齐缺失字段 |
| 5 | `frontend/src/store/notification.ts` | 从响应对象中提取 `.items` 数组，计算 `.unread_count` |

#### P1 修复清单

| # | 文件 | 修复内容 |
|---|------|---------|
| 6 | `frontend/src/api/filters.ts` | 调用时传 `dimension` 参数；`deleteFilterView` 改用 `del()` |
| 7 | `frontend/src/components/common/AdvancedFilter.vue` | 适配后端 `{ dimension, options[] }` 响应格式 |
| 8 | `frontend/src/api/ai.ts` | `recommendChart` 构造 `{ data_description, analysis_goal, top_k }` |
| 9 | `frontend/src/components/analysis/CorrelationAnalysis.vue` | 构造正确双指标请求；适配响应 `variable_x/variable_y` |
| 10 | `backend/app/api/correlations.py` | 响应字段 `metric_a/metric_b` → `variable_x/variable_y` |
| 11 | `backend/app/schemas/correlations.py` | `CorrelationAnalyzeResponse` 字段名对齐 |

#### P2 修复清单

| # | 文件 | 修复内容 |
|---|------|---------|
| 12 | `frontend/src/api/filters.ts` | `saveFilterView` 适配后端 `{ name, dashboard_id, filters, is_public }` |
| 13 | `frontend/src/types/api.ts` | `User` 接口 `department/created_at/last_login` 改为可选 |
| 14 | `frontend/src/store/auth.ts` | `logout()` 改为直接清理 localStorage，不调用 API |

### 任务 2：后台 UI 入口与可操作闭环

- 修复 `Sidebar.vue` 系统管理入口：补 `admin: '/admin'` 路由映射
- 重构 `AdminPage.vue` 信息架构，分 Tab：数据源配置 / 邮件同步 / Excel上传 / 同步历史 / 数据质量 / 用户与权限 / 审计日志
- 数据源保存必须支持 `connection_config`（IMAP、BI/ERP、内部系统、Excel）
- 前端枚举统一为后端接受值：`email_imap`、`bi_platform`、`erp`、`internal_system`、`excel`
- Excel 上传页补数据源选择、同步模式、上传后跳转/关联批次详情

### 任务 3：邮件同步入口产品化

- 后端新增同步管理 API：
  - `POST /api/v1/data-sync/email/run` — 立即触发邮件同步
  - `GET /api/v1/data-sync/jobs` — 同步任务列表
  - `GET /api/v1/data-sync/jobs/{id}` — 同步任务详情
  - `POST /api/v1/data-sync/jobs/{id}/retry` — 失败任务重试
  - `POST /api/v1/data-sync/email/test-connection` — 测试 IMAP 连接
- 前端新增"邮件同步"面板：测试连接/立即同步/只预览不入库按钮，同步结果展示

### 任务 4：后端整改

- 整理所有路由返回结构，确保 `{code, message, data, trace_id}` 一致
- 把 `dashboard.py`、`drilldowns.py` 中 placeholder 替换为真实指标来源
- 统一错误处理：业务错误抛标准异常或返回标准错误，不混用成功形态承载失败
- 补齐 Query DSL 的业务字段白名单、聚合能力、分页和注入防护
- 验证命令：`cd backend && D:/workspace/caiwu04/.venv/Scripts/python.exe -m pytest -q`

### 任务 5：前端整改

- 逐个修复 `frontend/src/api` 与后端实际契约不一致的封装
- 优先修复管理后台：`DataSourceList.vue` / `ExcelUploader.vue` / `DataQualityDashboard.vue`
- 同步 TypeScript 类型：ReportStatus、Drilldown 类型、AI 推荐返回、FilterView 等与后端 schema 对齐
- 对 Dashboard、Analysis、Report、Prediction、Admin、DrillDown 六条主链路做页面级联调
- 验证命令：`cd frontend && npm run build`

### 任务 6：集成测试与验收矩阵

- 建立 P0 契约测试：auth、dashboard、query、insights、filters、correlations、drilldowns、reports、predictions
- 建立端到端链路测试：登录→驾驶舱→筛选→洞察→钻取→报告→预测
- 建立 RBAC 矩阵：admin、analyst、viewer 的菜单、接口和数据访问边界
- 建立验收门禁：后端 pytest、前端 build、契约测试均通过才允许标记完成

---

## 四、修改文件总清单

| 优先级 | 文件路径 |
|--------|---------|
| P0 | `backend/app/schemas/query.py` |
| P0 | `backend/app/api/dashboard.py` |
| P0 | `backend/app/api/insights.py` |
| P0 | `backend/app/schemas/insights.py` |
| P0 | `frontend/src/store/notification.ts` |
| P1 | `frontend/src/api/filters.ts` |
| P1 | `frontend/src/components/common/AdvancedFilter.vue` |
| P1 | `frontend/src/api/ai.ts` |
| P1 | `frontend/src/components/analysis/CorrelationAnalysis.vue` |
| P1 | `backend/app/api/correlations.py` |
| P1 | `backend/app/schemas/correlations.py` |
| P2 | `frontend/src/api/filters.ts` (saveFilterView) |
| P2 | `frontend/src/types/api.ts` |
| P2 | `frontend/src/store/auth.ts` |

---

## 五、验收标准

- 前端 `npm run build` 在 `frontend` 目录通过，0错误
- 后端 `pytest -q` 在 `backend` 目录通过
- API 契约清单中 P0 路径、字段、状态与前后端代码一致
- Dashboard、Analysis、DrillDown、Report、Prediction、Admin 六条主链路完成联调
- 管理后台能从 UI 完成：进入后台→创建/编辑邮件数据源→测试IMAP连接→立即同步→查看同步历史
- 所有业务指标不得使用未标注的 placeholder/mock；无法计算时返回明确业务原因
- RBAC、审计、错误响应、trace_id 在关键写操作和权限接口中表现一致
