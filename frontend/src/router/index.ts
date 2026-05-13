import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/components/layout/DashboardLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/DashboardPage.vue'),
      },
      {
        path: 'metrics',
        name: 'CoreMetrics',
        component: () => import('@/views/CoreMetricsPage.vue'),
      },
      {
        path: 'trend-analysis',
        name: 'TrendAnalysis',
        component: () => import('@/views/TrendAnalysisPage.vue'),
      },
      {
        path: 'department-analysis',
        name: 'DepartmentAnalysis',
        component: () => import('@/views/DepartmentAnalysisPage.vue'),
      },
      {
        path: 'product-analysis',
        name: 'ProductAnalysis',
        component: () => import('@/views/ProductAnalysisPage.vue'),
      },
      {
        path: 'insights',
        name: 'Insights',
        component: () => import('@/views/InsightsPage.vue'),
      },
      {
        path: 'transactions',
        name: 'Transactions',
        component: () => import('@/views/TransactionsPage.vue'),
      },
      {
        path: 'drilldown/:report_id?',
        name: 'DrillDown',
        component: () => import('@/views/DrillDownPage.vue'),
      },
      {
        path: 'analysis',
        name: 'Analysis',
        component: () => import('@/views/AnalysisPage.vue'),
        meta: { requiresRole: ['admin', 'analyst'] },
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('@/views/ReportPage.vue'),
      },
      {
        path: 'prediction',
        name: 'Prediction',
        component: () => import('@/views/PredictionPage.vue'),
      },
      {
        path: 'mobile-no-drill',
        name: 'MobileNoDrill',
        component: () => import('@/views/MobileNoDrill.vue'),
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/AdminPage.vue'),
        meta: { requiresAuth: true, requiresRole: ['admin'] },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/ProfilePage.vue'),
        meta: { requiresAuth: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundPage.vue'),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Auth and role guard
router.beforeEach((to) => {
  const requiresAuth = to.matched.some((r) => r.meta.requiresAuth !== false);
  const token = localStorage.getItem('access_token');

  if (requiresAuth && !token) {
    return { name: 'Login', query: { redirect: to.fullPath } };
  }

  if (to.name === 'Login' && token) {
    return { path: '/' };
  }

  // Role-based access
  const requiresRole = to.meta.requiresRole as string[] | undefined;
  if (requiresRole && token) {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userRole = user?.role;
      if (userRole && !requiresRole.includes(userRole)) {
        return { name: 'Dashboard' };
      }
    } catch {
      // If user data is corrupt, let auth guard handle it
    }
  }

  return true;
});

export default router;
