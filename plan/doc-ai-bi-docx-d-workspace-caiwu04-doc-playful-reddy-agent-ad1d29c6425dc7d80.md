# Implementation Plan: 后台管理页面 + 数据管理组件

## Overview

Add admin page, profile page, 404 page, data management components, and API layer to the frontend. All new components follow existing Ant Design v4 patterns from the codebase.

## Files to Create (7 files)

### 1. `src/types/dataManagement.ts`
TypeScript interfaces for data management entities:
- `DataSource` (id, name, source_type, is_active, priority, last_sync_at, etc.)
- `DataQualitySummary` (total_checks, passed, warnings, failed, pass_rate)
- `DataQualityError` (id, source, field, error_type, message, severity, created_at)
- `UploadResult` (rows_parsed, rows_cleaned, rows_synced, errors)
- `ChangePasswordRequest` (old_password, new_password, confirm_password)

### 2. `src/api/dataManagement.ts`
API functions using existing `get/post/put/del` from `./request`:
- `getDataSources`, `getDataSource`, `createDataSource`, `updateDataSource`, `deleteDataSource`
- `getDataQualitySummary`, `getDataQualityErrors`
- `uploadExcel` (FormData upload with axios)
- `getUsers`, `createUser`, `updateUser`, `deleteUser` (for user management tab)
- `getAuditLogs` (for audit log tab)
- `changePassword`

Note: Hardcoded mock data will be used in components since APIs may not be ready.

### 3. `src/components/admin/DataSourceList.vue`
- `a-table` displaying DataSource items with columns: name, source_type (tag), is_active (switch), priority, last_sync_at
- "添加数据源" button -> modal form (name, source_type, priority)
- Row actions: edit (opens edit modal), delete (confirm popup)
- Empty state when no data sources
- Matches existing Ant Design patterns from Sidebar.vue

### 4. `src/components/admin/DataQualityDashboard.vue`
- 4 stat cards: total_checks, passed (green), warnings (orange), failed (red)
- `a-progress` showing pass_rate percentage
- `a-table` error logs with severity filter dropdown
- Empty state: "暂无数据质量记录"

### 5. `src/components/admin/ExcelUploader.vue`
- `a-upload-dragger` accepting .xlsx/.xls files
- Loading state during upload
- Result card: rows_parsed, rows_cleaned, rows_synced
- `a-alert` for errors
- Empty state: "拖拽或点击上传 Excel 文件"

### 6. `src/views/AdminPage.vue`
- `a-tabs` with tabs: 用户管理, 数据源, 数据质量, Excel 上传, 审计日志
- 用户管理 tab: inline `a-table` CRUD for users (username, email, role)
- 审计日志 tab: inline `a-table` with user, action, target, timestamp
- `a-alert` at top for non-admin users: "您没有权限访问管理后台"

### 7. `src/views/ProfilePage.vue`
- User info card: username, email, role (read-only from auth store)
- Change password form: old_password, new_password, confirm
- Matches LoginPage.vue Ant Design form style

### 8. `src/views/NotFoundPage.vue`
- `a-result` status="404" with subtitle and "返回首页" button

## Files to Modify (2 files)

### 9. `src/router/index.ts`
- Add `/profile` as child of DashboardLayout -> ProfilePage
- Add `/admin` as child of DashboardLayout -> AdminPage (meta: requiresRole: ['admin'])
- Add `/:pathMatch(.*)*` top-level catch-all -> NotFoundPage (placed last, no requiresAuth)
- Add "Profile" and "Admin" to page title mapping for TopBar

### 10. `src/components/layout/TopBar.vue`
- "个人中心" menu item: add `@click="router.push('/profile')"`
- "管理后台" menu item: add `v-if="authStore.isAdmin"` and `@click="router.push('/admin')"`
- Both items need explicit click handlers since <a-menu-item> doesn't auto-navigate

## Verification Steps

1. `npm run build` (vue-tsc --noEmit && vite build) passes with no errors
2. Navigate to `/profile` -> shows user info from auth store
3. Navigate to `/nonexistent` -> shows 404 page
4. Admin tab components show empty states properly
5. All changes are surgical — no modifications to unrelated code
