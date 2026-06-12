<template>
  <el-button
    :type="resolvedType"
    :size="size"
    :loading="loading"
    :disabled="disabled"
    :plain="plain"
    :text="text"
    :link="link"
    @click="$emit('click', $event)"
  >
    <el-icon v-if="resolvedIcon" class="pipeline-btn-icon"><component :is="resolvedIcon" /></el-icon>
    <slot>{{ resolvedLabel }}</slot>
  </el-button>
</template>

<script setup>
import { computed } from 'vue'
import { getAction, LAYER_BTN_TYPES } from '../../constants/actions'

const props = defineProps({
  action: { type: String, default: '' },
  layer: { type: String, default: '' },
  label: { type: String, default: '' },
  icon: { type: String, default: '' },
  type: { type: String, default: '' },
  size: { type: String, default: 'default' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  plain: { type: Boolean, default: false },
  text: { type: Boolean, default: false },
  link: { type: Boolean, default: false },
})

defineEmits(['click'])

const actionDef = computed(() => (props.action ? getAction(props.action) : null))

const resolvedLabel = computed(() => props.label || actionDef.value?.label || '')
const resolvedIcon = computed(() => props.icon || actionDef.value?.icon || '')
const resolvedType = computed(() => {
  if (props.type) return props.type
  if (actionDef.value?.type) return actionDef.value.type
  if (props.layer && LAYER_BTN_TYPES[props.layer]) return LAYER_BTN_TYPES[props.layer]
  return 'default'
})
</script>

<style scoped>
.pipeline-btn-icon {
  margin-right: 4px;
  vertical-align: -2px;
}
</style>
