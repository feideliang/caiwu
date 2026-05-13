# AI+BI 数智化财务管报系统 — Team Leader 汇报（交叉审查整改版）

**汇报日期：** 2026-05-08
**汇报人：** 项目管理AI助手
**文档版本：** V4.0（最终整改汇总 — V3.0 + PM + Architect + Testing 三团队整合）

---

## 一、项目概述

### 核心目标
构建"BI全量呈现 + AI智能解读 + 专家策略校准"的新型管报体系，试点场景为**收入毛利智能分析驾驶舱**。

### 技术栈
- **前端：** Vue3 + ECharts + Ant Design Vue（18个组件、10个页面）
- **后端：** Python FastAPI + PostgreSQL + Redis + Celery（33个API端点）
- **AI服务：** LangChain + 千问API（5大AI能力）
- **数据源：** 邮件附件Excel（IMAP自动读取）

---

## 二、交叉审查发现

本次交叉审查由前端工程师、后端工程师、测试工程师三方并行开展，重点审查：
1. 前端组件与后端API的一一对应关系
2. 后端API设计是否覆盖前端全部数据需求
3. 测试用例是否覆盖所有前端交互与后端接口

### 2.1 总体结论

| 审查维度 | 现状 | 问题 |
|---------|------|------|
| 前后端对齐率 | 约35%（6/18组件完全对齐） | 12个组件缺后端API支撑或契约不一致 |
| 后端API完整度 | 6个详细设计 / 33个声称 | 27个API仅提及或未设计 |
| 测试覆盖率 | 约28%（按API维度） | 仅dashboard、attribution、drill-down有测试示例 |
| 产品语义一致性 | 低 | attribution→correlation方向未同步、dashboard聚合vs查询模型冲突 |

---

## 三、前后端对齐整改

### 3.1 前端组件 → 后端API 映射表

| 前端组件 | 需要的API | 后端状态 | 整改优先级 |
|---------|----------|---------|-----------|
| DashboardLayout | 无直接API | 无需整改 | - |
| Sidebar | 用户角色/菜单权限 | 缺失 | P0 |
| TopBar | 用户信息/通知 | 缺失 | P1 |
| KpiCard | dashboard/metrics | 已设计 | 已对齐 |
| ChartWidget | dashboard/metrics/predictions | 部分对齐 | P0 |
| AIChartRecommender | recommend-chart, recommend-layout | 缺失 | P0 |
| InsightCard | insights列表/状态流转 | 缺失 | P0 |
| FinancialOverview | dashboard+insights+recommend | 部分对齐 | P0 |
| AdvancedFilter | filter-options, data/query, filter-views | 缺失 | P0 |
| MobileDrawer | 复用筛选API | 缺失 | P0 |
| TransactionAnalysis | 5个交易分析API | 缺失 | P1 |
| LargeAmountTable | transactions/large-amounts | 缺失 | P1 |
| AnomalyAlertList | 交易异常列表 | 缺失 | P1 |
| CorrelationAnalysis | analyze-correlation, correlations | 不一致 | P0 |
| CorrelationMatrix | correlations | 不一致 | P0 |
| CalibrationPanel | correlation/:id/calibrate | 缺失 | P0 |
| DrillDown_L1~L4 | 4层钻取路由化API | 部分对齐 | P0 |
| ReportCenter | report生成/列表/下载 | 部分对齐 | P1 |
| ForecastChart | predict | 缺失 | P1 |
| ConfidenceBand | predict区间 | 缺失 | P1 |
| DataSourceList | 数据源CRUD | 缺失 | P2 |
| DataQualityDashboard | 质量统计/错误日志 | 缺失 | P2 |
| ExcelUploader | 手动上传API | 缺失 | P2 |

### 3.2 后端有但前端未消费的API

| 后端API | 前端消费情况 | 建议 |
|---------|------------|------|
| `GET /api/v1/metrics` | 前端未明确绑定 | 保留，定位为聚合接口 |
| `POST /api/v1/ai/attribution` | 前端已降级为correlation | **废弃**，改为correlation |
| `POST /api/v1/ai/qa` | 前端无问答页面 | 降级为内部能力 |
| `DELETE /api/v1/cache/invalidate` | 无前端消费 | 运维接口，保留 |
| `GET /api/v1/dashboard` | 前端模型已调整 | 保留或重定位BFF层 |

### 3.3 核心契约不一致点（必须整改）

#### 问题1：Dashboard 数据入口不匹配
- **后端：** 单一聚合大包 `GET /api/v1/dashboard`
- **前端：** 期望 `POST /api/data/query` + `GET /api/insights` 组合
- **整改：** 保留dashboard作为快速聚合接口，同时新增query+insights支撑组件化渲染

#### 问题2：Drill-down 路径设计不匹配
- **后端：** `GET /api/v1/drill-down?level=&parent_path=`
- **前端：** `GET /api/drilldown/:level/:id/detail` 路由模型
- **整改：** 后端重构为资源化接口，与前端四层路由一致

#### 问题3：Attribution vs Correlation
- **后端：** 仍设计 `POST /api/v1/ai/attribution`
- **前端：** 已改为相关性分析 + 人工校准
- **整改：** 后端正式废弃attribution，新建correlation体系

#### 问题4：Report API 模型不匹配
- **后端：** 单次同步生成 `POST /api/v1/ai/report`
- **前端：** 报告中心需要列表/预览/下载/状态
- **整改：** 后端改为异步任务型资源

---

## 四、后端整改方案

### 4.1 API重构清单（按优先级）

#### P0级（联调阻断，必须首先补齐）

| 序号 | API | 方法+路径 | 对应前端组件 | 说明 |
|------|-----|----------|------------|------|
| 1 | 图表推荐 | `POST /api/v1/ai/recommend-chart` | AIChartRecommender | 规则预筛+AI精排 |
| 2 | 布局推荐 | `POST /api/v1/ai/recommend-layout` | AIChartRecommender | 按设备类型推荐 |
| 3 | 洞察列表 | `GET /api/v1/insights` | InsightCard | 支持type/status/pagination |
| 4 | 洞察状态 | `POST /api/v1/insights/{id}/status` | InsightCard | read/process/ignore |
| 5 | 筛选元数据 | `GET /api/v1/filter-options` | AdvancedFilter | 动态选项+级联 |
| 6 | 统一查询 | `POST /api/v1/query` | 所有页面 | Filter DSL统一查询 |
| 7 | 筛选视图 | `GET/POST/DELETE /api/v1/filter-views` | AdvancedFilter | 保存/切换/删除 |
| 8 | 相关分析 | `POST /api/v1/correlations/analyze` | CorrelationAnalysis | 替代attribution |
| 9 | 相关列表 | `GET /api/v1/correlations` | CorrelationAnalysis | 历史分析结果 |
| 10 | 人工校准 | `POST /api/v1/correlations/{id}/calibrate` | CalibrationPanel | confirm/doubt/reject |
| 11 | 钻取L1 | `GET /api/v1/drilldowns/{report_id}/summary` | DrillDown_L1 | 公司层汇总 |
| 12 | 钻取L2 | `GET /api/v1/drilldowns/{report_id}/departments` | DrillDown_L2 | 部门层 |
| 13 | 钻取L3 | `GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products` | DrillDown_L3 | 产品层 |
| 14 | 钻取L4 | `GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products/{product_id}/records` | DrillDown_L4 | 交易明细 |
| 15 | 钻取明细 | `GET /api/v1/drilldowns/records/{record_id}` | DrillDown_L4 | 单条详情 |
| 16 | 用户信息 | `GET /api/v1/auth/me` | Sidebar/TopBar | 角色/菜单权限 |
| 17 | 登录 | `POST /api/v1/auth/login` | 全局 | JWT认证 |

#### P1级（功能增强，Phase 2补齐）

| 序号 | API | 对应前端组件 | 说明 |
|------|-----|------------|------|
| 18 | 预测 | `POST /api/v1/predictions` + `GET /api/v1/predictions/{id}` | ForecastChart | 含拒绝规则 |
| 19 | 报告生成 | `POST /api/v1/reports` | ReportCenter | 异步任务 |
| 20 | 报告列表 | `GET /api/v1/reports` | ReportCenter | 历史报告 |
| 21 | 报告下载 | `GET /api/v1/reports/{id}/download` | ReportCenter | Word/PDF |
| 22 | 合同汇总 | `GET /api/v1/transactions/contracts` | TransactionAnalysis | 合同维度 |
| 23 | 订单汇总 | `GET /api/v1/transactions/orders` | TransactionAnalysis | 订单维度 |
| 24 | 项目汇总 | `GET /api/v1/transactions/projects` | TransactionAnalysis | 项目维度 |
| 25 | 异常交易 | `GET /api/v1/transactions/anomalies` | TransactionAnalysis | 规则标记 |
| 26 | 大额交易 | `GET /api/v1/transactions/large-amounts` | LargeAmountTable | 阈值筛选 |

#### P2级（管理面，Phase 3补齐）

| 序号 | API | 对应前端组件 | 说明 |
|------|-----|------------|------|
| 27-30 | 数据源CRUD | DataSourceList | `GET/POST/PUT/DELETE /api/v1/data-sources` |
| 31 | 质量统计 | `GET /api/v1/data-quality/summary` | DataQualityDashboard | 汇总数据 |
| 32 | 错误日志 | `GET /api/v1/data-quality/errors` | DataQualityDashboard | 明细查询 |
| 33 | 手动上传 | `POST /api/v1/uploads/excel` | ExcelUploader | 手动补录 |

### 4.2 废弃/调整的后端API

| 原API | 处理 | 替代 |
|-------|------|------|
| `POST /api/v1/ai/attribution` | **废弃** | `POST /api/v1/correlations/analyze` |
| `POST /api/v1/ai/qa` | 降级内部能力 | 暂不暴露前端 |
| `GET /api/v1/dashboard` | 保留，重定位BFF | 与query共存 |
| `GET /api/v1/metrics` | 保留，聚合接口 | 与query共存 |
| `GET /api/v1/drill-down` | 废弃 | 新drilldowns资源化接口 |

### 4.3 新增数据库表

| 表名 | 用途 | 关联API |
|------|------|--------|
| insight | 洞察记录+状态流转 | insights |
| filter_view | 筛选视图保存 | filter-views |
| correlation_result | 相关性分析结果 | correlations |
| correlation_calibration | 人工校准记录 | calibrate |
| prediction_result | 预测结果+置信区间 | predictions |
| report_task | 报告异步任务 | reports |

---

## 五、前端整改方案

### 5.1 前端组件调整清单

| 组件 | 调整内容 | 优先级 |
|------|---------|--------|
| AIChartRecommender | 新增，联调recommend-chart/recommend-layout | P0 |
| InsightCard | 新增，联调insights CRUD | P0 |
| AdvancedFilter | 新增，联调filter-options/query/views | P0 |
| CorrelationAnalysis | 适配correlation API（非attribution） | P0 |
| CalibrationPanel | 新增，联调calibrate API | P0 |
| DrillDown_L1~L4 | 适配drilldowns资源化API路径 | P0 |
| FinancialOverview | 改为dashboard+insights+recommend组合消费 | P0 |
| TransactionAnalysis | 分阶段：Phase 1复用drill L4，Phase 2联调transactions API | P1 |
| ReportCenter | 适配report异步任务模型 | P1 |
| PredictionPage | 适配predict API+拒绝规则UI | P1 |

### 5.2 前端API联调策略

| 阶段 | 可联调API | 前端组件 | 状态 |
|------|----------|---------|------|
| Phase 1 | dashboard, drill-down(旧), metrics | KpiCard, ChartWidget(基础) | 当前可联调 |
| Phase 1新增 | insights, filter-options, query, auth/me | AIChartRecommender, InsightCard, AdvancedFilter | 待后端开发 |
| Phase 2 | drilldowns(新), correlations, calibrate | DrillDown_L1~L4, CorrelationAnalysis, CalibrationPanel | 待后端重构 |
| Phase 2新增 | transactions/*, predict, reports | TransactionAnalysis, PredictionPage, ReportCenter | 待后端开发 |
| Phase 3 | data-sources, data-quality, uploads | DataSourceList, DataQualityDashboard, ExcelUploader | 待后端开发 |

---

## 六、测试用例整改方案

### 6.1 当前测试覆盖现状

| 维度 | 已有覆盖 | 缺失 |
|------|---------|------|
| 后端API | 2-3个有示例(dashboard, attribution, drill-down弱覆盖) | 30+个API无测试 |
| 前端组件 | 页面级基本覆盖 | 交互级/响应式/权限缺失 |
| 契约测试 | 无 | 前后端接口契约未锁定 |
| 性能测试 | 目标声明，无详细场景 | 复杂DSL/上传/异步流 |

### 6.2 新增测试用例（138个）

按模块分解：

| 模块 | 新增用例数 | 重点内容 |
|------|-----------|---------|
| AIChartRecommender | 10 | 推荐渲染/应用/降级/三端适配 |
| InsightCard | 9 | 状态流转/钻取跳转/图表联动 |
| AdvancedFilter | 11 | AND/OR/保存视图/移动端/DSL校验 |
| TransactionAnalysis | 7 | Tab切换/大额高亮/异常联动 |
| CorrelationAnalysis | 9 | 相关矩阵/AI解释/校准闭环 |
| Drill-down页面化 | 10 | 深链接/前进后退/面包屑/空数据 |
| PredictionPage | 8 | 置信区间/拒绝规则/降级UI |
| DataManagement | 8 | 上传/批次/质量/错误 |
| 响应式布局 | 7 | web/tablet/mobile断点 |
| 权限RBAC | 6 | admin/analyst/viewer矩阵 |
| 后端API端点 | 30 | 33个端点全覆盖 |
| 契约测试 | 10 | 9大资源域schema锁定 |
| 性能稳定性 | 5 | DSL查询/上传/异步报告 |

### 6.3 调整后测试总数

| 类别 | 数量 |
|------|------|
| 已有基线 | 55+ |
| 新增用例 | 138 |
| **调整后总计** | **193+** |

### 6.4 测试类型分布

| 测试类型 | 用例数 | 占比 |
|---------|-------|------|
| Unit | ~28 | 15% |
| Integration/API | ~69 | 36% |
| E2E | ~47 | 24% |
| Responsive | ~14 | 7% |
| Permission | ~16 | 8% |
| Contract | ~10 | 5% |
| Performance | ~9 | 5% |

### 6.5 测试执行优先级

1. **P0后端集成+契约测试** — API正确性、鉴权、DSL、预测拒绝规则
2. **P0前端E2E** — AIChartRecommender、InsightCard、AdvancedFilter、Drill-down
3. **响应式+RBAC矩阵** — 三端适配+角色权限
4. **性能稳定性** — 复杂查询、上传、异步报告
5. **P1/P2补充用例** — 细节完善

---

## 七、整改后关键指标对比

| 指标 | V2.0 | V3.0（整改后） |
|------|------|---------------|
| 前后端对齐率 | ~35% | 100%（API清单+契约锁定） |
| 后端API详细设计 | 6个 | 33个（P0:17, P1:9, P2:7） |
| 废弃API | 0个 | 5个（attribution/旧drill-down等） |
| 新增数据库表 | 9张 | +6张（insight/correlation等） |
| 测试用例数 | 55+ | 193+ |
| 测试API覆盖率 | ~28% | 100% |
| 契约测试覆盖 | 无 | 9大资源域 |
| 响应式测试 | 无 | 7个专项用例 |
| 权限测试 | 无 | 6个专项用例 |

---

## 八、下一步行动

1. **确认整改方案：** 请Team Leader审查本交叉审查整改报告
2. **后端启动API设计：** 按P0→P1→P2优先级输出OpenAPI契约文档
3. **前端适配准备：** 基于新API清单调整组件props和联调顺序
4. **测试矩阵落地：** 将193+用例拆分为Vitest/Playwright/Pytest/k6四套测试套件
5. **契约先行：** 前后端先锁定API schema（可使用OpenAPI/Swagger），再并行开发
6. **迭代评审：** 每阶段联调后检查对齐率和测试覆盖率

---

**汇报完毕，请审批。**

---

## 九、最终整改工单与开发计划 (V4.0 Unified Plan)

**编制日期：** 2026-05-08
**编制人：** 协调AI
**来源文件：**
- PM remediation: `pm-remediation-tasklist-v3-1.md`
- Architect remediation: 嵌入于 V3.0 本文件第四～六节
- Testing remediation: `doc-ai-bi-docx-d-workspace-caiwu04-doc-playful-reddy-agent-a625e1f6f3c9184cf.md`

### 9.1 整改工单总览

| 团队 | 工单范围 | 数量 | 说明 |
|------|---------|------|------|
| PM | PM-001 ~ PM-015 | 15 | 产品决策、范围定义、优先级调整、UX 规范 |
| 架构师 | AR-001 ~ AR-013 | 13 | API 设计、数据库表、前后端对齐、架构模式 |
| 测试 | QA-001 ~ QA-012 | 12 | 66 个具体测试用例，覆盖并发/安全/缓存/降级/SLA |
| **合计** | | **40** | |

#### PM 工单优先级分布

| 优先级 | 数量 | 工单 ID |
|--------|------|---------|
| P0 | 12 | PM-001, PM-002, PM-003, PM-006, PM-007, PM-008, PM-009, PM-010, PM-011, PM-012, PM-014, PM-015 |
| P1 | 3 | PM-004, PM-005, PM-013 |

#### 架构师工单列表

| ID | 标题 | 优先级 |
|----|------|--------|
| AR-001 | P0 级 17 个 API 端点详细设计（OpenAPI 契约） | P0 |
| AR-002 | P1 级 9 个 API 端点设计（报告/预测/交易分析） | P1 |
| AR-003 | P2 级 7 个 API 端点设计（数据源/质量/上传） | P2 |
| AR-004 | 废弃 5 个旧 API（attribution/旧drill-down/qa等） | P0 |
| AR-005 | 新增 6 张数据库表设计与迁移脚本 | P0 |
| AR-006 | 前端 11 个组件适配清单 | P0 |
| AR-007 | 双数据路径策略（Dashboard BFF + Query API） | P0 |
| AR-008 | 钻取 API 重构为 RESTful 资源化路径 | P0 |
| AR-009 | 废弃 attribution，新建 correlation 体系 | P0 |
| AR-010 | 报告生成异步任务架构（Celery + 状态机） | P0 |
| AR-011 | 配置管理 MVP — 环境变量方案 | P0 |
| AR-012 | 测试矩阵基线定义（193+ 用例） | P0 |
| AR-013 | RBAC 权限系统设计与实现 | P0 |

#### 测试工单优先级分布

| 优先级 | 数量 | 工单 ID | 用例数 |
|--------|------|---------|--------|
| P0 | 5 | QA-001, QA-002, QA-003, QA-004, QA-005, QA-009 | 36 |
| P1 | 5 | QA-006, QA-007, QA-008, QA-010, QA-011 | 27 |
| P2 | 1 | QA-012 | 3 |
| **合计** | **12** | | **66** |

---

### 9.2 前后端开发任务分解

#### 9.2.1 前端开发任务

| 任务 ID | 描述 | 优先级 | 依赖 | 验收标准 |
|---------|------|--------|------|---------|
| FE-001 | **Sidebar 组件 — 用户角色/菜单权限** | P0 | AR-013 (RBAC) | 根据用户角色动态渲染菜单项；viewer 不可见管理入口 |
| FE-002 | **AIChartRecommender 组件** | P0 | AR-001 (recommend-chart/layout API) | 推荐渲染/应用/降级正常；web/tablet/mobile 三端适配 |
| FE-003 | **InsightCard 组件** | P0 | AR-001 (insights API) | 状态流转 (read/process/ignore)；钻取跳转；图表联动 |
| FE-004 | **AdvancedFilter 组件** | P0 | AR-001 (filter-options/query/views API) | AND/OR 组合筛选；保存视图；DSL 校验；移动端适配 |
| FE-005 | **CorrelationAnalysis + CalibrationPanel** | P0 | AR-009 (correlation 体系) | 相关矩阵渲染；AI 解释展示；校准闭环 (confirm/doubt/reject) |
| FE-006 | **DrillDown L1~L4 组件** | P0 | AR-008 (RESTful drill API) | 深链接支持；前进后退；面包屑导航；空数据处理 |
| FE-007 | **FinancialOverview 组件改造** | P0 | AR-007 (双路径策略) | 改为 dashboard + insights + recommend 组合消费模式 |
| FE-008 | **ReportCenter — 异步任务列表与状态** | P0 | PM-007, AR-010 | 任务列表/状态徽章/筛选 Tab；自动轮询 (5s/10s)；分页 |
| FE-009 | **ReportCenter — 步骤进度指示器** | P0 | PM-006 | 4 步进度条 (数据收集→AI分析→文档生成→完成)；状态图标；不显示百分比 |
| FE-010 | **ReportCenter — 取消与重试** | P0 | PM-008, PM-009 | pending 可取消；running 取消中；failed 可重试；retry_count >= 3 置灰 |
| FE-011 | **TopBar 通知铃铛** | P1 | PM-005 | 未读红点；下拉列表；点击标记已读；点击跳转 ReportCenter |
| FE-012 | **数据新鲜度指示器** | P0 | PM-012 | TopBar 显示 "更新于 HH:MM"；fresh/stale/error 颜色区分；手动刷新按钮 60s cooldown |
| FE-013 | **Mobile 钻取禁用** | P1 | PM-013 | 屏幕 < 768px 时钻取入口置灰；Toast 提示；直接访问 URL 弹 Dialog |
| FE-014 | **响应式布局验证** | P1 | - | web/tablet/mobile 三端断点测试通过 |
| FE-015 | **TransactionAnalysis / LargeAmountTable / AnomalyAlertList** | P1 (Phase 2) | AR-002 (交易分析 API) | Tab 切换；大额高亮；异常联动 |
| FE-016 | **ForecastChart + ConfidenceBand** | P0 (升级为 P0) | AR-002 (predict API) | 预测曲线+置信区间渲染；拒绝规则 UI；降级提示 |
| FE-017 | **DataSourceList / DataQualityDashboard / ExcelUploader** | P2 (Phase 3) | AR-003 | 数据源 CRUD；质量统计面板；手动上传 |

#### 9.2.2 后端开发任务

| 任务 ID | 描述 | 优先级 | 依赖 | 验收标准 |
|---------|------|--------|------|---------|
| BE-001 | **P0 级 17 个 API 端点实现** | P0 | AR-001 | OpenAPI 契约锁定；鉴权/DSL/分页/错误处理完整 |
| BE-002 | **P1 级 API — 报告异步任务** | P0 (升级) | AR-010, PM-006~009 | Celery task + 状态机；step 追踪；cancel/retry 支持；report_task 表 |
| BE-003 | **P1 级 API — 预测** | P0 (升级) | AR-002 | predict endpoint；拒绝规则；prediction_result 表 |
| BE-004 | **P1 级 API — 交易分析（5 个端点）** | P1 (Phase 2) | AR-002 | contracts/orders/projects/anomalies/large-amounts |
| BE-005 | **废弃 API 清理** | P0 | AR-004 | 删除 attribution 端点；旧 drill-down 重定向；qa 标记内部 |
| BE-006 | **钻取 API 重构** | P0 | AR-008 | 从 query param 改为 RESTful 路径；L1~L4 路由化 |
| BE-007 | **Correlation 体系新建** | P0 | AR-009 | analyze/correlations/calibrate 三个端点；correlation_result + calibration 表 |
| BE-008 | **双数据路径实现** | P0 | AR-007, PM-011 | Dashboard BFF (Redis 缓存, TTL=300s) + Query API (直查 DB)；同源 DAO |
| BE-009 | **数据库表迁移脚本** | P0 | AR-005 | 6 张新表 (insight/filter_view/correlation_result/correlation_calibration/prediction_result/report_task) + audit_log + users/roles |
| BE-010 | **RBAC 权限系统** | P0 | AR-013 | users/roles 表；JWT 鉴权；role-based 数据过滤；/auth/login + /auth/me |
| BE-011 | **审计日志 (audit_log)** | P0 | AR-013 | 所有写操作记录；user_id/timestamp/action/resource/before/after |
| BE-012 | **通知 API** | P1 | PM-005 | GET /api/v1/notifications + POST /{id}/read；分页 limit=20 |
| BE-013 | **数据新鲜度 API** | P0 | PM-012 | GET /api/v1/system/data-freshness；last_sync_time/data_range/status/next_sync_at |
| BE-014 | **配置管理 MVP** | P0 | PM-010, AR-011 | 环境变量加载验证；.env.example 模板；API Key 不泄露到前端 |
| BE-015 | **P2 级 API — 数据源/质量/上传** | P2 (Phase 3) | AR-003 | data-sources CRUD；data-quality summary/errors；uploads/excel |
| BE-016 | **统一错误响应格式** | P0 | - | 所有 API 返回 {code, message, data}；无堆栈跟踪泄露 |

---

### 9.3 开发阶段更新 (V4.0)

#### Phase 1 — MVP 核心交付（P0 + 升级 P0）

| 模块 | 内容 |
|------|------|
| 认证与权限 | JWT 登录、/auth/me、RBAC（admin/analyst/viewer） |
| 核心 API | 17 个 P0 端点：推荐、洞察、筛选、查询、相关性、钻取、认证 |
| 报告生成 | 异步任务架构（Celery）、步骤进度指示器、任务列表、取消/重试 |
| 前瞻预测 | predict API、拒绝规则、置信区间渲染、降级 UI |
| 数据路径 | Dashboard BFF（Redis 缓存）+ Query API（直查 DB） |
| 数据新鲜度 | TopBar 新鲜度指示器、手动刷新、时间范围显示 |
| 通知框架 | TopBar 通知铃铛（最小实现）、通知 API |
| 审计日志 | audit_log 表、写操作全记录 |
| 配置管理 | 环境变量方案、.env.example、API Key 安全管理 |
| 钻取 | L1~L4 RESTful API、移动端禁用策略 |
| **新增数据库表** | insight, filter_view, correlation_result, correlation_calibration, prediction_result, report_task, audit_log, users, roles |

#### Phase 2 — 功能增强（P1）

| 模块 | 内容 |
|------|------|
| 交易分析 | 5 个交易分析 API、TransactionAnalysis/LargeAmountTable/AnomalyAlertList 组件 |
| 配置 UI | 报告模板配置、预测参数、告警阈值、数据源设置的管理界面 |
| NL2SQL 激活 | 语义层 Schema 设计、NL2SQL 准确率评测基线 (>80%)、安全审查、前端问答页面 |
| 邮件通知 | 报告完成邮件通知基础设施 |
| 高级通知 | 完整通知类型系统、批量标记、通知偏好设置 |

#### Phase 3 — 管理与优化（P2）

| 模块 | 内容 |
|------|------|
| 数据源管理 | 数据源 CRUD、质量仪表板、手动 Excel 上传 |
| 性能优化 | 数据库索引优化、查询计划分析、慢查询日志 |
| 可访问性/国际化 | a11y 合规、i18n 支持（中英文） |
| 高级特性 | 自定义图表类型、高级筛选表达式导出 |

#### Phase 4 — UAT 与上线准备

| 模块 | 内容 |
|------|------|
| UAT | 用户验收测试、真实数据验证、业务场景 E2E |
| 数据归档 | 历史数据归档策略、冷数据迁移 |
| 废弃清理 | Phase 1/2 临时代码、降级兼容代码移除 |
| 上线检查 | 安全审查、性能压测、部署文档、运维手册 |

---

### 9.4 关键 API 路径统一规范

所有 API 端点统一使用 `/api/v1/` 前缀，版本控制通过 URL 路径实现。

| 资源域 | 路径模式 | 示例 |
|--------|---------|------|
| 认证 | `/api/v1/auth/*` | POST /api/v1/auth/login, GET /api/v1/auth/me |
| 数据查询 | `/api/v1/query` | POST /api/v1/query |
| 仪表板 | `/api/v1/dashboard` | GET /api/v1/dashboard |
| 洞察 | `/api/v1/insights` | GET /api/v1/insights, POST /api/v1/insights/{id}/status |
| 筛选 | `/api/v1/filter-options`, `/api/v1/filter-views` | GET/POST/DELETE |
| 相关性分析 | `/api/v1/correlations` | POST /api/v1/correlations/analyze, POST /api/v1/correlations/{id}/calibrate |
| 钻取 | `/api/v1/drilldowns/*` | GET /api/v1/drilldowns/{report_id}/summary, GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products |
| AI 推荐 | `/api/v1/ai/*` | POST /api/v1/ai/recommend-chart, POST /api/v1/ai/recommend-layout |
| 预测 | `/api/v1/predictions` | POST /api/v1/predictions, GET /api/v1/predictions/{id} |
| 报告 | `/api/v1/reports` | POST /api/v1/reports, GET /api/v1/reports, POST /api/v1/reports/{id}/cancel, GET /api/v1/reports/{id}/download |
| 通知 | `/api/v1/notifications` | GET /api/v1/notifications, POST /api/v1/notifications/{id}/read |
| 系统 | `/api/v1/system/*` | GET /api/v1/system/data-freshness |
| 数据同步 | `/api/v1/data-sync/*` | POST /api/v1/data-sync/refresh |
| 交易分析 | `/api/v1/transactions/*` | GET /api/v1/transactions/contracts, /orders, /projects, /anomalies, /large-amounts |
| 数据源管理 | `/api/v1/data-sources` | GET/POST/PUT/DELETE /api/v1/data-sources |
| 数据质量 | `/api/v1/data-quality/*` | GET /api/v1/data-quality/summary, /errors |
| 上传 | `/api/v1/uploads/*` | POST /api/v1/uploads/excel |

**废弃/内部 API（不暴露前端）：**
- `POST /api/v1/ai/attribution` — 已废弃，替代为 correlation
- `POST /api/v1/ai/qa` — 降级为内部能力，Phase 2 激活
- `GET /api/v1/drill-down` — 已废弃，替代为新 drilldowns 路径
- `DELETE /api/v1/cache/invalidate` — 运维接口，保留

---

### 9.5 新增数据库表清单

**原始 9 张表（V2.0 已有）：**
1. `financial_data` — 财务核心数据
2. `data_batch` — 数据批次记录
3. `data_source` — 数据源配置
4. `data_quality_log` — 数据质量日志
5. `chart_config` — 图表配置
6. `dashboard_layout` — 仪表板布局
7. `user_preference` — 用户偏好
8. `system_config` — 系统配置
9. `sync_job` — 同步任务记录

**V3.0 新增 6 张表：**
10. `insight` — 洞察记录 + 状态流转 (type, status, content, created_at)
11. `filter_view` — 筛选视图保存 (user_id, name, filter_condition, created_at)
12. `correlation_result` — 相关性分析结果 (metric_pair, coefficient, ai_explanation, created_at)
13. `correlation_calibration` — 人工校准记录 (correlation_id, user_id, decision, comment)
14. `prediction_result` — 预测结果 + 置信区间 (metric, forecast_data, confidence_level, rejection_reason)
15. `report_task` — 报告异步任务 (user_id, report_type, date_range, status, current_step, task_id, celery_task_id, retry_count, parent_task_id, created_at, completed_at)

**V4.0 新增 2 张表：**
16. `audit_log` — 审计日志 (user_id, action, resource, resource_id, before_value, after_value, ip_address, created_at)
17. `users` — 用户表 (username, password_hash, email, role_id, is_active, last_login, created_at)
18. `roles` — 角色表 (role_name, permissions, description, created_at)
19. `notification` — 通知表 (user_id, type, title, content, is_read, created_at, read_at)

**总计：19 张表**（含原始 9 + V3.0 新增 6 + V4.0 新增 4）

---

### 9.6 测试矩阵更新

| 类别 | 用例数 | 说明 |
|------|--------|------|
| V3.0 基线 | 193+ | 前端组件/后端API/契约/响应式/RBAC/性能 |
| QA 新增 | 66 | 并发(6) + 数据同步(5) + 缓存(5) + Celery容错(7) + 安全(8) + 大文件(6) + 数据质量(5) + 监控(5) + 降级(5) + SLA(6) + UX(5) + 新鲜度(3) |
| **合计** | **259+** | 全量测试覆盖 |

#### 测试执行 Sprint 规划

| Sprint | 天数 | 工单 | 并行度 | 重点 |
|--------|------|------|--------|------|
| Sprint 1 | 5 天 | QA-001, QA-004, QA-009 | 2 人 | P0 阻断类：并发、Celery 容错、降级模式 |
| Sprint 2 | 5 天 | QA-005, QA-002, QA-003 | 2 人 | P0 安全类：渗透测试、数据同步、缓存一致性 |
| Sprint 3 | 7 天 | QA-006, QA-007, QA-008, QA-010, QA-011 | 3 人 | P1 功能类：大文件、数据质量、监控、SLA、UX |
| Sprint 4 | 3 天 | QA-012 + 全量回归 | 1 人 | P2 完善 + 回归测试 |
| **总计** | **20 天** | 12 工单 / 66 用例 | | |

#### PM-014 补充测试用例（20 个）

**并发测试 (6 用例):**
- 多用户同时生成报告（5 并发）
- 多用户同时提交筛选查询
- 同一用户并发取消+重试
- Dashboard BFF 缓存命中/未命中并发
- 并发 Excel 上传批次隔离
- JWT token 并发刷新

**安全测试 (6 用例):**
- SQL 注入防护 — query API DSL 参数
- 越权访问 — viewer 访问 admin 接口
- XSS 防护 — 报告内容注入
- CSRF 防护 — 跨域 POST
- API Key 泄露防护
- 文件上传类型校验

**缓存测试 (4 用例):**
- Dashboard BFF 缓存 TTL 过期刷新
- 缓存失效后首次响应 <2s
- 手动刷新绕过缓存
- Redis 宕机降级直查 DB

**大文件边界测试 (4 用例):**
- 50MB Excel 拒绝（413）
- 10MB/10万行 Excel 处理
- 单次查询 10万+ 行分页
- 报告生成异常数据量超时

---

### 9.7 关键决策汇总

| 决策 ID | 内容 | 影响范围 |
|---------|------|---------|
| DEC-01 | NL2SQL 正式延期至 Phase 2 | API 降级内部、前端无消费代码 |
| DEC-02 | 报告生成/前瞻预测升 P0，交易分析降 Phase 2 | 交付优先级、资源分配 |
| DEC-03 | 异步任务 UX 最小定义 (A-E)，邮件通知延期 | 前端组件范围 |
| DEC-04 | 配置管理 MVP 走环境变量，Phase 2 再建 UI | 后端实现方式 |
| DEC-05 | 双数据路径：Query API 为主，Dashboard BFF 为缓存优化 | 架构模式 |
| DEC-06 | 数据新鲜度：TopBar 全局 + Dashboard 页面级指示 | 前端+后端 |
| DEC-07 | 移动端禁用钻取，Toast 提示 | 前端响应式策略 |

---

**V4.0 变更日志（V3.0 → V4.0）：**
1. 整合 PM 15 个工单（DEC-01~07 决策落地）
2. 整合架构师 13 个工单（API/DB/架构对齐）
3. 整合测试 12 个工单、66 个用例
4. 报告生成、前瞻预测从 P1 升 P0
5. 交易分析从 P1 降为 Phase 2
6. NL2SQL 正式标记 Phase 2 延期
7. TopBar 通知框架纳入 Phase 1（最小实现）
8. 配置管理 MVP 确认为环境变量方案
9. 新增审计日志表、users/roles 表、notification 表
10. 测试矩阵从 193+ 扩展至 259+
11. API 路径统一 `/api/v1/` 前缀规范
12. 移动端钻取策略正式确定

---

---
---

## 十、蜂群并行开发计划 (Swarm Mode V5.0)

**编制日期：** 2026-05-08
**模式：** 5 Agent 并行开发，Team Leader 统一协调

### 当前完成状态

| 模块 | 后端 | 前端 | 测试 |
|------|------|------|------|
| 认证 + RBAC | 7 endpoints (auth + users CRUD) | LoginPage, Sidebar, TopBar | 206 unit pass |
| Dashboard | 2 endpoints (bff + insights) | KpiCard, ChartWidget, FinancialOverview | 部分 API 测试 |
| AI 推荐 | 2 endpoints (chart + layout) | AIChartRecommender | 无测试文件 |
| 洞察 | 3 endpoints | InsightCard | 有 API 测试 |
| 筛选 | 4 endpoints | AdvancedFilter | 有 API 测试 |
| 相关性 | 3 endpoints | CorrelationAnalysis, Matrix, Calibration | 有 API 测试 |
| 钻取 | 5 endpoints (L1-L4) | DrillDown_L1~L4 | 有 API 测试 |
| 报告 | 6 endpoints | ReportCenter | 有 API 测试 |
| 预测 | 2 endpoints | PredictionPage | 有 API 测试 |
| 通知 | 3 endpoints | TopBar 铃铛 | 无测试文件 |
| 审计日志 | 1 endpoint | 管理页待建 | 无测试文件 |
| 系统 | 1 endpoint | 新鲜度指示器 | 无测试文件 |
| 交易分析 | **待开发** | **待开发** | **待开发** |
| 数据源管理 | **待开发** | **待开发** | **待开发** |
| 数据质量 | **待开发** | **待开发** | **待开发** |
| Excel上传 | **待开发** | **待开发** | **待开发** |

### 5 Agent 并行分工

#### Agent 1 — Backend Phase 2: 交易分析 + 缺失测试
**创建:** `app/api/transactions.py`, `app/schemas/transactions.py`, `app/services/transaction_service.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/transactions/contracts` | GET | 合同汇总，按 entity 分组 AR/AP |
| `/api/v1/transactions/orders` | GET | 订单汇总，按 period revenue/cost |
| `/api/v1/transactions/projects` | GET | 项目汇总，entity revenue/cost/profit |
| `/api/v1/transactions/anomalies` | GET | 异常检测，>2sigma 标记 |
| `/api/v1/transactions/large-amounts` | GET | 大额交易，threshold 筛选 |

**新测试文件:** `tests/test_api_transactions.py`, `tests/test_api_notifications.py`, `tests/test_api_audit.py`, `tests/test_api_system.py`, `tests/test_api_query.py`, `tests/test_api_ai.py`, `tests/test_api_users.py`

**修复:** conftest.py asyncpg 并发冲突 (test_engine session→function scope)

#### Agent 2 — Backend Phase 3: 数据管理 + 上传
**创建:** `app/api/data_sources.py`, `app/api/data_quality.py`, `app/api/uploads.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/data-sources` | GET/POST | 数据源列表 / 创建 |
| `/api/v1/data-sources/{id}` | GET/PUT/DELETE | 数据源详情/更新/软删除 |
| `/api/v1/data-quality/summary` | GET | 质量汇总 (passed/warnings/failed) |
| `/api/v1/data-quality/errors` | GET | 错误日志分页列表 |
| `/api/v1/uploads/excel` | POST | Excel 上传→解析→清洗→同步 |

#### Agent 3 — Frontend Phase 2: 交易分析 + Bug 修复
**修复 3 个 bug:**
- `MobileDrawer.vue` — `props.open = false` → `emit('update:open', false)`
- `AIChartRecommender.vue` — 模板双引号转义
- `CorrelationAnalysis.vue` — 缺失 `<style>` 块

**新建组件:**
- `src/api/transactions.ts` — 5 个交易分析 API 函数
- `src/store/transactions.ts` — 交易分析 Pinia store
- `src/components/analysis/TransactionAnalysis.vue` — Tab 容器
- `src/components/analysis/LargeAmountTable.vue` — 大额表格
- `src/components/analysis/AnomalyAlertList.vue` — 异常列表

#### Agent 4 — Frontend Phase 3: 管理页面 + 数据管理
**新建组件:**
- `src/api/dataManagement.ts` — 数据源/质量/上传 API
- `src/components/admin/DataSourceList.vue` — 数据源管理表格
- `src/components/admin/DataQualityDashboard.vue` — 质量看板
- `src/components/admin/ExcelUploader.vue` — 拖拽上传

**新建页面:**
- `src/views/AdminPage.vue` — 管理后台 (用户/数据/质量/上传/审计)
- `src/views/ProfilePage.vue` — 个人中心/改密
- `src/views/NotFoundPage.vue` — 404

**路由更新:** `src/router/index.ts` 添加 /admin, /profile, /:pathMatch(404)

#### Agent 5 — 集成测试 + 契约验证
- 修复 conftest.py fixture scope 冲突
- 修复 3 个 auth 测试断言 (401 vs 403)
- 新建 `tests/test_api_contracts.py` — schema 契约校验
- 全量回归: pytest tests/ -v --tb=short

### 依赖关系

```
Agent 1 ──┬── Agent 3 (API 联调) ──┐
Agent 2 ──┴── Agent 4 (API 联调) ──┤
Agent 3 (独立, 可 mock 先行)  ─────┤
Agent 4 (独立, 可 mock 先行)  ─────┤
Agent 5 (依赖 1+2 完成) ──────────┘
```

### 验收入口
- 后端: `pytest tests/ -v --tb=short` 全量通过
- 前端: `npm run build` 无 TS 错误
- 联调: `POST /api/v1/auth/login` → token → 调所有 API
- 前端: 浏览器访问所有页面无白屏

