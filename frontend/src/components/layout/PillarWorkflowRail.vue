<template>
  <nav v-if="showRail" class="pillar-rail" aria-label="五层智能体流水线">
    <span class="pillar-rail-label">L1→L5</span>
    <template v-for="(step, idx) in steps" :key="step.layer">
      <button
        type="button"
        class="pillar-step"
        :class="{ 'is-active': isActive(step) }"
        :title="step.desc"
        @click="go(step)"
      >
        <span class="pillar-dot" aria-hidden="true"></span>
        <span>{{ step.label }}</span>
      </button>
      <div v-if="idx < steps.length - 1" class="pillar-connector" aria-hidden="true"></div>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PILLAR_STEPS, getPillarStepPath, isPillarStepActive } from '../../constants/navigation'

const route = useRoute()
const router = useRouter()

const steps = PILLAR_STEPS

const HIDE_ON = ['/login', '/canvas']

const showRail = computed(() => !HIDE_ON.some(p => route.path.startsWith(p)))

function isActive(step) {
  return isPillarStepActive(step, route.path)
}

function go(step) {
  const path = getPillarStepPath(step)
  if (route.path !== path) router.push(path)
}
</script>
