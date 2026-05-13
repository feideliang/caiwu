# 当前项目完成情况、差距原因与整改计划

## 背景与目标

本计划基于 `rule.md` 的谨慎、简化、外科手术式整改原则，对当前代码库与 `plan\` 目录下 V4.0 规划进行对照，目标是识别“当前实现与计划相距深远”的根因，并给出可执行的整改计划与分工。

项目当前已经不是空壳：`backend\app` 中已存在 FastAPI 路由、统一响应、RBAC、审计、报告、预测、交易、钻取、筛选、相关性、数据源/质量/上传等模块；`frontend\src` 中也已存在 Vue3 页面、API 层、Pinia store、仪表盘、报告中心、管理页、分析组件等。但现状更接近“多批计划被局部实现后的拼装版”，尚未达到 `plan\` 中 V4.0 对“契约锁定、前后端完全对齐、AI+BI 核心闭环、测试矩阵落地”的目标。

## 当前完成情况判断

### 已完成或基本具备

| 领域 | 当前状态 |
| --- | --- |
| 后端骨架 | FastAPI 应用、路由聚合、数据库模型、Alembic 初始迁移、统一响应结构已存在。 |
| 认证与权限 | `/auth/login`、`/auth/me`、用户 CRUD、JWT/RBAC 相关代码已存在。 |
| 核心资源 API | insights、filters、query、correlations、drilldowns、reports、predictions、transactions、notifications、system、data-sources、data-quality、uploads 等文件已存在。 |
| 前端页面与组件 | Dashboard、Analysis、Report、Prediction、Admin、Profile、NotFound、DrillDown 等页面和主要组件已存在。 |
| 测试基线 | `backend\tests` 下已有较多 pytest 用例，覆盖 API、服务、安全、报告、预测、数据处理等。 |
| 邮件同步后端能力 | 已有 `app\tasks\email_poll.py`、`app\services\email_reader.py`，具备 IMAP 拉取附件并走 parse → clean → sync 管道的雏形。 |

### 与 V4.0 规划仍明显不一致

| 差距类别 | 典型问题 |
| --- | --- |
| Dashboard 运行时契约不匹配 | 后端 Dashboard BFF 返回 `{ dashboard_id, dashboard_name, device_type, charts, layout }`，前端期望 `{ kpis, charts, updated_at }`；KPI 缺失会导致 4 个 KPI 卡片显示 0，图表字段也不匹配。 |
| 通知响应结构不匹配 | 后端通知接口返回分页对象 `{ items, total, unread_count, ... }`，前端 store 若直接当数组使用，会导致 TopBar badge 和通知列表异常。 |
| 洞察字段不匹配 | 后端 insights 返回 `title/content/insight_type` 等基础字段，前端需要 `description/severity/confidence/related_metric` 用于卡片渲染和颜色展示。 |
| API 路径不一致 | 计划写 `POST /api/v1/ai/recommend-chart`、`/recommend-layout`，当前前后端实现为 `/ai/recommend/chart`、`/ai/recommend/layout`。 |
| 前后端契约不一致 | Drilldown 前端 `getDrillProducts(reportId, params)` 调 `/drilldowns/{reportId}/products`，后端要求 `/drilldowns/{report_id}/departments/{dept_id}/products`；单条记录前端调 `/records/{id}`，后端是 `/drilldowns/records/{id}`。 |
| Filter 契约不匹配 | `filter-options` 后端要求 `dimension` 参数并返回 `{ dimension, options, total }`，前端存在无参调用和期望 `{ fields }` 的风险；`filter-views` 保存/删除字段与方法也不一致。 |
| AI/Correlation 请求字段不匹配 | AI 推荐、相关性分析的前端请求字段与后端 schema 不一致，容易造成 422 或页面无结果。 |
| Auth 类型不匹配 | 登录返回的 user 字段少于前端类型定义；`authStore.logout()` 若调用不存在的 API logout，会产生运行时错误。 |
| 查询模型偏离规划 | 计划是 dimensions/metrics/filters 的统一查询 DSL，当前后端 `query.py` 是按 `table + fields + filters` 的通用表查询，偏技术表模型，未形成业务语义层。 |
| 报告状态机不一致 | 计划状态包含 collecting_data、ai_analyzing、document_generating、cancelling 等；前端仍使用 pending/generating/completed/failed/cancelled 的简化模型。 |
| 数据语义仍有占位 | `dashboard.py`、`drilldowns.py` 中仍有 placeholder 聚合，例如成本按收入 60% 估算；这会造成业务指标无法验收。 |
| AI 能力实现深度不足 | 相关性解释存在 mock fallback；图表推荐更偏规则/评分，未形成可配置 AI 服务降级策略与验收指标。 |
| 审计/错误处理不够一致 | 部分接口返回 `APIResponse.error`，部分抛异常，个别审计失败被吞掉；与计划中的错误码、异常、trace 一致性要求仍有距离。 |
| 测试与计划矩阵不匹配 | 当前已有测试，但没有看到前端 Vitest/Playwright、契约测试、响应式/RBAC 矩阵、性能测试等完整落地。 |
| UI 入口与操作闭环缺失 | API 和任务文件已存在，但后台页面没有把“保存配置、测试连接、手动同步、同步历史、错误查看”串起来；用户看到的是零散表格和上传，不是可用后台。 |
| 后台保存能力不足 | `DataSourceList.vue` 只保存 name/source_type/priority，没有暴露 `connection_config`，无法配置 IMAP host、port、账号、过滤规则，也没有保存后校验。 |
| 邮件同步无入口 | 后端只有 Celery `email_poll.poll_emails` 定时任务，没有面向 UI 的“立即同步邮件/查看同步状态/查看处理 UID/重试失败批次”API 和按钮。 |
| 管理入口不完整 | `Sidebar.vue` 显示“系统管理”，但 `menuRouteMap` 没有 `admin: '/admin'`，侧边栏点击不会进入后台；后台入口主要藏在 TopBar 用户菜单。 |
| 枚举/字段大小写风险 | 前端数据源类型使用 `EMAIL_IMAP`、`BI_PLATFORM`，后端模型枚举值是 `email_imap`、`bi_platform` 等小写值，保存时可能校验失败或数据不一致。 |
| 验证环境受阻 | 当前工具环境缺少 `pwsh`，无法实际执行 `npm run build` 与 pytest；后续本地验证应明确使用当前目录 `.venv`。 |

## 相距深远的主要原因

1. **计划先于契约固化，开发按局部理解推进。** `plan\` 中同时存在 V4.0 总计划、后端详细计划和多个局部前端计划，部分实现采用了局部命名，例如 `/ai/recommend/chart`，未回收成统一 API 规范。
2. **缺少“契约为单一事实源”。** 前端 API 封装、后端路由、Pydantic schema、测试用例之间没有统一 OpenAPI/契约测试作为硬门禁，导致路径、字段、状态枚举逐步漂移。
3. **任务被按页面/模块拆开，而不是按端到端业务闭环拆开。** 代码中很多模块文件存在，但从“驾驶舱展示 -> 筛选 -> 洞察 -> 钻取 -> 报告/预测 -> 通知/审计”的完整链路看，仍有断点。
4. **UI 没有按后台作业流设计。** 管理端只实现了“数据源列表/Excel 上传/质量表格”的静态入口，但缺少企业后台最关键的保存、测试、触发、反馈、重试、历史追踪，所以即使 API 存在，用户仍无法完成真实操作。
5. **邮件同步被当成后台定时任务，没有产品化。** `email_poll` 能跑定时同步，但没有手动触发 API、同步记录表、前端按钮、进度反馈、错误重试入口，也没有和数据源配置页面打通。
6. **占位实现没有被纳入技术债清单。** placeholder、mock fallback、简化状态机、成本估算等能让页面跑起来，但没有后续强制替换任务，导致“看似完成”和“可验收完成”差距扩大。
7. **测试目标从数量计划变成了局部覆盖。** 后端 pytest 文件较多，但计划中的 259+ 测试矩阵还要求契约、前端交互、E2E、响应式、权限、性能等，目前未形成统一完成口径。
8. **环境验证未标准化。** 用户明确要求使用当前目录 `.venv` 和本地 `.env`，说明此前执行口径可能不统一；若 CI/本地/开发环境不一致，会持续放大“计划通过、落地失败”的问题。

## 整改原则

- **先收敛契约，再改代码。** 不继续新增功能，先把路径、字段、状态、错误码、分页、权限统一。
- **按端到端闭环验收。** 每批整改必须能从前端页面触发到后端、数据库、响应、错误处理、测试全部闭环。
- **先补 UI 操作闭环，再扩功能。** 当前优先级不是继续堆 API，而是让已有 API/任务在后台页面可配置、可触发、可观察、可重试。
- **保留已完成代码，做最小兼容整改。** 不大拆重写，优先加兼容路由、修前端封装、补 schema 和测试。
- **清理占位必须显式排期。** placeholder/mock 只能作为降级策略存在，不能伪装成业务完成。

## 整改计划

### 任务 1：范围冻结与完成口径统一

**负责人：PM / 技术负责人**

- 将 `plan\doc-ai-bi-docx-d-workspace-caiwu04-doc-playful-reddy.md` 中 V4.0 作为主计划，其余 agent 计划作为参考，不再并行扩展范围。
- 形成一张“V4.0 功能清单 -> 当前文件 -> API -> 测试 -> 验收状态”的对照表。
- 明确当前阶段只整改 P0 + 已实现但不一致的 P1/P2，不新增新的业务功能。
- 输出统一完成定义：接口契约一致、前后端调用成功、测试覆盖、无 placeholder 业务结果、可用本地 `.env + .venv` 验证。
- 将“后台可操作闭环”列为 P0 完成口径：管理员必须能在 UI 中配置数据源、保存配置、测试连接、触发同步、查看结果和错误。

### 任务 1A：后台 UI 入口与可操作闭环优先整改

**负责人：前端负责人 + 后端负责人**

- 修复 `Sidebar.vue` 的系统管理入口：补 `admin: '/admin'` 路由映射，并在选中态中加入 Admin/Profile/Prediction 等页面标题映射。
- 重构 `AdminPage.vue` 信息架构，把后台拆成清晰 Tab：
  - 数据源配置
  - 邮件同步
  - Excel 上传
  - 同步历史
  - 数据质量
  - 用户与权限
  - 审计日志
- 数据源保存必须支持 `connection_config`：
  - IMAP：host、port、user、password/密钥引用、use_xoauth2、subject_keywords、from_whitelist、max_attachment_size、processed_uid_file。
  - BI/ERP/内部系统：base_url、认证方式、token/密钥引用、同步频率。
  - Excel：默认上传来源、模板说明、字段映射。
- 前端枚举统一为后端接受值：`email_imap`、`bi_platform`、`erp`、`internal_system`、`excel`，显示层再翻译为中文。
- 数据源保存后必须刷新列表并展示后端返回的校验错误；不能只用 `message.success` 假定成功。
- Excel 上传页补数据源选择、同步模式选择、上传后跳转/关联批次详情。

### 任务 1B：邮件同步入口产品化

**负责人：后端负责人 + 前端负责人 + 数据/运维负责人**

- 后端新增同步管理 API，建议路径：
  - `POST /api/v1/data-sync/email/run`：立即触发邮件同步；支持指定 `source_id`、是否只处理最新邮件、是否 dry-run。
  - `GET /api/v1/data-sync/jobs`：同步任务列表，展示来源、触发方式、状态、开始/结束时间、处理行数、错误数。
  - `GET /api/v1/data-sync/jobs/{id}`：同步任务详情，包含附件、批次、错误明细、质量结果。
  - `POST /api/v1/data-sync/jobs/{id}/retry`：失败任务重试。
  - `POST /api/v1/data-sync/email/test-connection`：使用数据源配置测试 IMAP 连接和搜索规则。
- 将现有 `email_poll.poll_emails` 复用为服务层能力，避免 UI 手动同步和 Celery 定时同步走两套逻辑。
- 用 `sync_job` / `data_batch` / `data_quality_log` 记录邮件同步全过程，补齐 email_uid、subject、from、attachment、rows_synced、error_message。
- 前端新增“邮件同步”面板：
  - 显示当前邮件数据源配置状态。
  - “测试连接”“立即同步”“只预览不入库”按钮。
  - 展示最近同步结果、处理附件、成功/失败行数、错误明细。
  - 提供失败重试和跳转数据质量日志。
- TopBar 数据新鲜度增加“手动刷新/同步”入口，但要受 RBAC 控制，viewer 只读。

### 任务 2：API 契约审计与路径/字段收敛

**负责人：后端负责人 + 前端负责人 + QA**

- 以 `/api/v1` 为唯一前缀，列出实际后端路由与前端 API 封装差异。
- 先按运行时影响重排修复优先级：
  - P0：页面崩溃、KPI 为 0、图表无数据、TopBar badge 异常、Insights 渲染异常。
  - P1：功能按钮失效、422、空结果、保存/删除失败。
  - P2：类型字段缺失、兼容性和显示细节。
- 优先修复已发现的不一致：
  - Dashboard BFF：`DashboardBFFResponse` 补 `kpis`、`updated_at`；`ChartDataItem` 对齐前端 `id/title/type/data/options`，或前端统一适配后端字段。
  - Notifications：前端 store 从 `data.data.items` 取数组，并使用 `unread_count` 更新未读数。
  - Insights：后端补 `description/severity/confidence/related_metric`，或前端建立统一 mapper，避免直接渲染 undefined。
  - Filter options：明确是后端改为一次返回全部 fields，还是前端按 dimension 分批请求；不要保留两套隐式结构。
  - AI 推荐路径：统一 `/ai/recommend-chart`、`/ai/recommend-layout` 或明确保留当前路径并同步计划。
  - AI 推荐字段：统一 `data_type/data_sample/device` 与 `data_description/analysis_goal/top_k`，避免前端请求 422。
  - Correlation：统一 `variables/date_from/date_to` 与 `metric_a/metric_b/method/period_start/period_end`；响应字段统一 `metric_a/metric_b` 或 `variable_x/variable_y`。
  - Drilldown 路径：修复前端 `products/records` 调用与后端 RESTful 路径不一致。
  - Filter view 删除：前端从 `POST /filter-views/{id}/delete` 改为后端 `DELETE /filter-views/{id}`，或后端补兼容路由。
  - Filter view 保存：前端从 `{ name, conditions, logic }` 转换为后端 `{ name, dashboard_id, filters, is_public }`。
  - Auth：前端 User 类型中后端未返回字段设为可选；logout 先本地清理 token/user，不依赖不存在的后端接口。
  - Query DSL：决定继续 `table` 查询模型，还是回到计划中的 dimensions/metrics 业务 DSL。
  - Report 状态：前端、后端、类型定义统一状态枚举和进度步骤。
- 生成 OpenAPI 快照或契约清单，作为后续测试与联调基线。

### 任务 2A：P0 契约修复文件清单

**负责人：后端负责人 + 前端负责人**

| 优先级 | 文件 | 修复目标 |
| --- | --- | --- |
| P0 | `backend\app\schemas\query.py` | `DashboardBFFResponse` 补齐 KPI、更新时间和前端图表字段，或明确输出 mapper schema。 |
| P0 | `backend\app\api\dashboard.py` | 从 `financial_data` 聚合真实 KPI，不再让前端 KPI 永远为 0。 |
| P0 | `backend\app\api\insights.py` | 输出前端卡片所需 `description/severity/confidence/related_metric`。 |
| P0 | `backend\app\schemas\insights.py` | Schema 与实际响应、前端类型对齐。 |
| P0 | `frontend\src\store\notification.ts` | 适配分页对象，使用 `.items` 和 `.unread_count`。 |
| P1 | `frontend\src\api\filters.ts` | `filter-options` 参数、`deleteFilterView` HTTP 方法、`saveFilterView` 字段转换对齐后端。 |
| P1 | `frontend\src\components\common\AdvancedFilter.vue` | 适配后端 filter options 返回结构，避免无参 422。 |
| P1 | `frontend\src\api\ai.ts` | 统一 AI 推荐请求字段。 |
| P1 | `frontend\src\components\analysis\CorrelationAnalysis.vue` | 构造后端接受的双指标请求，并适配响应字段。 |
| P1 | `backend\app\api\correlations.py` | 相关性响应字段与前端类型统一。 |
| P1 | `backend\app\schemas\correlations.py` | 相关性请求/响应 schema 与 UI 一致。 |
| P2 | `frontend\src\types\api.ts` | User 可选字段与后端登录响应对齐。 |
| P2 | `frontend\src\store\auth.ts` | logout 改成本地清理或补齐后端 logout API。 |

### 任务 3：后端整改

**负责人：后端负责人**

- 整理所有路由返回结构，确保 `{code, message, data, trace_id}` 一致。
- 把 `dashboard.py`、`drilldowns.py` 中成本估算、简单聚合等 placeholder 替换为真实指标来源；如数据源暂缺，接口必须返回明确的不可计算原因，而不是伪造业务值。
- 统一错误处理：业务错误抛标准异常或返回标准错误，不混用成功形态承载失败；审计失败不能静默吞掉，应按项目日志策略记录。
- 补齐 Query DSL 的业务字段白名单、聚合能力、分页和注入防护。
- 对报告、预测、通知、审计形成完整状态机与审计链路。
- 本地验证命令固定为：
  - `D:\workspace\caiwu04\.venv\Scripts\python.exe -m pytest -q`（在 `backend` 目录执行）

### 任务 4：前端整改

**负责人：前端负责人**

- 逐个修复 `frontend\src\api` 与后端实际契约不一致的封装。
- 优先修复管理后台：
  - `Sidebar.vue` 系统管理点击无效。
  - `DataSourceList.vue` 缺少连接配置字段、测试连接、启停状态切换、保存错误展示。
  - `ExcelUploader.vue` 缺少 source_id/sync_mode UI、批次详情、错误行展示。
  - `DataQualityDashboard.vue` 与后端字段对齐，后端返回的是 `detail`，当前前端/后端存在 `message` 字段风险。
- 同步 TypeScript 类型：ReportStatus、Drilldown 类型、AI 推荐返回、FilterView、QueryResponse、PredictionResult 等必须与后端 schema 对齐。
- 将页面中的简化状态和硬编码逻辑替换为后端状态机驱动。
- 对 Dashboard、Analysis、Report、Prediction、Admin、DrillDown 六条主链路做页面级联调。
- 增加最小前端测试策略：至少覆盖 API 封装类型、关键组件状态渲染、权限入口显示、报告状态流转。
- 本地验证命令固定为：
  - `npm run build`（在 `frontend` 目录执行）

### 任务 5：集成测试与验收矩阵补齐

**负责人：QA 负责人**

- 先建立 P0 契约测试：auth、dashboard、query、insights、filters、correlations、drilldowns、reports、predictions。
- 增加运行时回归断言：
  - Dashboard 登录后 KPI 不全为 0，图表有可渲染数据结构。
  - Notifications 未读数来自 `unread_count`，通知列表来自 `items`。
  - InsightCard 不出现 undefined 文案，severity/confidence 有默认或后端值。
  - FilterOptions 不触发 422。
  - AI 推荐和相关性分析请求不触发 schema 校验错误。
- 再补端到端链路测试：
  - 登录后进入驾驶舱。
  - 筛选条件驱动查询。
  - 洞察列表读取和状态更新。
  - 相关性分析与人工校准。
  - 钻取 L1-L4。
  - 报告创建、轮询、取消、重试、下载。
  - 预测提交与结果/拒绝规则展示。
- 建立 RBAC 矩阵：admin、analyst、viewer 的菜单、接口和数据访问边界。
- 建立验收门禁：后端 pytest、前端 build、契约测试、关键 E2E 均通过才允许标记完成。

### 任务 6：交付治理与分工节奏

**负责人：技术负责人 + PM**

- 每批整改只关闭一组端到端链路，不按“文件已创建”统计完成。
- 每次合并必须附带：改动契约、影响页面、验证命令、剩余风险。
- 建立技术债清单，专门跟踪 placeholder/mock/fallback/路径兼容层；兼容层必须有移除条件。
- 对 `.env`、`.env.example`、本地 `.venv`、数据库迁移、seed 数据建立统一说明，确保开发与验收环境一致。
- 本地验证数据优先直接使用 `doc\` 目录下的 Excel，不再额外造一套重复样本，避免口径漂移。

## 建议分工表

| 角色 | 主要责任 | 首批交付物 |
| --- | --- | --- |
| PM | 范围冻结、优先级裁剪、验收口径 | V4.0 功能状态表、P0/P1/P2 边界确认 |
| 技术负责人 | 契约裁决、跨端整改顺序、技术债治理 | API 契约基线、端到端整改看板 |
| 后端负责人 | 路由/schema/服务/状态机/真实业务数据 | 修复路径契约、Query DSL、报告状态机、placeholder 清理 |
| 前端负责人 | API 封装、类型、页面状态、后台操作闭环、联调 | 修复后台入口、数据源保存、邮件同步入口、API 调用和统一类型 |
| QA 负责人 | 契约测试、E2E、RBAC、回归门禁 | P0 测试矩阵与本地执行脚本 |
| 数据/运维负责人 | `.env`、数据库迁移、seed、Redis/Celery/AI Key、IMAP 配置 | 本地可复现环境说明、邮件测试数据源、同步验证数据 |

## 验收标准

- 前端 `npm run build` 可在 `frontend` 目录通过。
- 后端 `D:\workspace\caiwu04\.venv\Scripts\python.exe -m pytest -q` 可在 `backend` 目录通过。
- API 契约清单中 P0 路径、字段、状态、错误码与前后端代码一致。
- Dashboard、Analysis、DrillDown、Report、Prediction、Admin 至少六条主链路完成联调。
- 管理后台必须能从 UI 完成：进入后台、创建/编辑邮件数据源、测试 IMAP 连接、立即同步邮件、查看同步历史、查看质量错误、重试失败任务。
- 所有业务指标不得使用未标注的 placeholder/mock；无法计算时返回明确业务原因。
- RBAC、审计、错误响应、trace_id 在关键写操作和权限接口中表现一致。

## 当前阻塞与注意事项

- 前后端服务已在本地启动（3000 / 8000），下一步优先做页面与 API 的联动冒烟检查。
- 已补邮件同步最小闭环：后端 `data-sync` 路由提供批次列表、立即同步、IMAP 连通性测试；前端后台页新增“邮件同步”Tab。
- 当前工具环境报告 `pwsh.exe` 不可用，因此本次无法实际完成构建/测试命令执行；后续应在本机 shell 中按上述 `.venv` 与本地 `.env` 口径验证。
- 本计划不建议立刻新增功能，应先做契约收敛与端到端闭环修复，否则会继续扩大“文件数量完成、业务链路未完成”的差距。
