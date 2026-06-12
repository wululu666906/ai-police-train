<template>
  <el-config-provider :locale="studentElementLocale">
    <div class="student-app">
      <div class="student-shell">
        <StudentSidebar />

        <div class="student-content">
          <StudentTopbar
            :display-name="displayName"
            :can-back-to-admin="canBackToAdmin"
            @back-admin="router.push('/admin/dashboard')"
            @logout="logout"
          />

          <main class="student-main" :class="{ 'student-main--scrollable': mainScrollable }">
            <router-view v-slot="{ Component }">
              <transition appear name="fade-transform" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </main>
        </div>
      </div>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, provide, ref } from 'vue'
import { useRouter } from 'vue-router'
import StudentSidebar from '../geeker-adapt/components/StudentSidebar.vue'
import StudentTopbar from '../geeker-adapt/components/StudentTopbar.vue'
import { studentElementLocale } from '../geeker-adapt/setupElementPlus'
import { clearAuth } from '../utils/auth'
import '../geeker-adapt/styles/common.scss'
import '../geeker-adapt/styles/student-theme.scss'
import '../geeker-adapt/styles/element-student.scss'

const router = useRouter()

const displayName = computed(() => localStorage.getItem('username') || '学员')
const canBackToAdmin = computed(() => localStorage.getItem('role') === 'admin')
const mainScrollable = ref(false)

const setMainScrollable = (value: boolean) => {
  mainScrollable.value = value
}

provide('setMainScrollable', setMainScrollable)

const logout = () => {
  clearAuth()
  router.push('/login')
}
</script>

<style scoped lang="scss">
.student-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.student-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
  background: var(--student-page-bg, #f0f2f5);
}

.student-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;

  &--scrollable {
    overflow: auto;
  }
}
</style>
