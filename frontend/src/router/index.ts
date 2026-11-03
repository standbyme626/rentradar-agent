import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '@/features/admin/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/share/:token',
      name: 'share',
      component: () => import('@/features/chat/ShareView.vue'),
      meta: { title: '只读看板', public: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/features/auth/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/',
      name: 'chat',
      component: () => import('@/features/chat/ChatView.vue'),
      meta: { title: '一句话找房' },
    },
    {
      path: '/admin',
      component: AdminLayout,
      redirect: '/admin/overview',
      meta: { requiresAdmin: true },
      children: [
        {
          path: 'overview',
          name: 'admin-overview',
          component: () => import('@/features/admin/OverviewView.vue'),
          meta: { title: '总览', crumb: '概览 / 总览' },
        },
        {
          path: 'candidates',
          name: 'admin-candidates',
          component: () => import('@/features/admin/CandidatesView.vue'),
          meta: { title: '候选工作台', crumb: '数据 / 候选工作台' },
        },
        {
          path: 'commute',
          name: 'admin-commute',
          component: () => import('@/features/admin/CommuteBudgetView.vue'),
          meta: { title: '通勤与预算', crumb: '数据 / 通勤与预算' },
        },
        {
          path: 'quality',
          name: 'admin-quality',
          component: () => import('@/features/admin/QualityView.vue'),
          meta: { title: '数据质量', crumb: '数据 / 数据质量' },
        },
        {
          path: 'reputation',
          name: 'admin-reputation',
          component: () => import('@/features/admin/ReputationView.vue'),
          meta: { title: '口碑证据', crumb: '数据 / 口碑证据' },
        },
        {
          path: 'providers',
          name: 'admin-providers',
          component: () => import('@/features/admin/ProvidersView.vue'),
          meta: { title: 'API 管理', crumb: '运营 / API 管理' },
        },
        {
          path: 'agent',
          name: 'admin-agent',
          component: () => import('@/features/admin/AgentMonitorView.vue'),
          meta: { title: 'Agent 监控', crumb: 'Agent / 会话与工具' },
        },
        {
          path: 'images',
          name: 'admin-images',
          component: () => import('@/features/admin/ImagesView.vue'),
          meta: { title: '图片 / AI', crumb: '内容 / 图片与 AI' },
        },
        {
          path: 'ops',
          name: 'admin-ops',
          component: () => import('@/features/admin/OpsView.vue'),
          meta: { title: '运维', crumb: '运营 / 运维' },
        },
        {
          path: 'tasks',
          name: 'admin-tasks',
          component: () => import('@/features/admin/TasksView.vue'),
          meta: { title: '采集任务', crumb: '运营 / 采集任务' },
        },
        {
          path: 'logs',
          name: 'admin-logs',
          component: () => import('@/features/admin/LogsView.vue'),
          meta: { title: '运行日志', crumb: '运营 / 运行日志' },
        },
        {
          path: 'settings',
          name: 'admin-settings',
          component: () => import('@/features/admin/SettingsView.vue'),
          meta: { title: '设置', crumb: '运营 / 设置' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  await auth.ensureLoaded()
  if (to.name === 'login') {
    if (!auth.user) return true
    const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : '/'
    return redirect.startsWith('/') ? redirect : '/'
  }
  if (!auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { path: '/' }
  }
  return true
})

router.afterEach((to) => {
  document.title = `${(to.meta.title as string) ?? 'RentRadar'} · RentRadar`
  let robots = document.querySelector('meta[name="robots"]')
  if (to.meta.public) {
    if (!robots) {
      robots = document.createElement('meta')
      robots.setAttribute('name', 'robots')
      document.head.appendChild(robots)
    }
    robots.setAttribute('content', 'noindex, nofollow, noarchive')
  } else if (robots) {
    robots.remove()
  }
})

export default router
