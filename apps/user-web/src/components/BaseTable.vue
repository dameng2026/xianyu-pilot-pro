<template>
  <div class="base-table-scroll">
  <table class="base-table">
    <thead>
      <tr>
        <th v-if="selectable" class="col-select" @click="onHeaderSelectClick">
          <input
            type="checkbox"
            class="bt-checkbox"
            :checked="allSelected"
            :indeterminate.prop="someSelected"
            :disabled="!rows || rows.length === 0"
            aria-label="全选"
            @click.stop
            @change="toggleAll"
          />
        </th>
        <th v-for="c in columns" :key="c.key">{{ c.title }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-if="!rows?.length">
        <td :colspan="(columns?.length || 1) + (selectable ? 1 : 0)">
          <slot name="empty">
            <div class="table-empty">暂无数据</div>
          </slot>
        </td>
      </tr>
      <tr v-for="(row, idx) in rows" :key="rowKey(row, idx)" :class="rowClass?.(row, idx) || ''" @click="$emit('row-click', row)">
        <td v-if="selectable" class="col-select" @click.stop="onRowSelectClick(row, idx, $event)">
          <input
            type="checkbox"
            class="bt-checkbox"
            :checked="isRowSelected(row, idx)"
            :aria-label="'选择第 ' + (idx + 1) + ' 行'"
            @click.stop
            @change="toggleRow(row, idx)"
          />
        </td>
        <td v-for="c in columns" :key="c.key">
          <slot :name="c.key" :row="row">{{ row[c.key] }}</slot>
        </td>
      </tr>
    </tbody>
  </table>
  </div>
</template>
<script setup>
import { computed } from 'vue'

const props = defineProps({
  columns: Array,
  rows: Array,
  rowClass: Function,
  // 是否开启行选择（opt-in，默认关闭，向后兼容）
  selectable: { type: Boolean, default: false },
  // 行唯一标识函数，用于 v-model:selectedKeys
  rowKey: { type: Function, default: (row, idx) => idx },
  // 选中行的 key 数组，配合 v-model:selectedKeys 使用
  selectedKeys: { type: Array, default: () => [] }
})
const emit = defineEmits(['row-click', 'update:selectedKeys'])

const rowKeys = computed(() => (props.rows || []).map((r, i) => props.rowKey(r, i)))
const selectedSet = computed(() => new Set(props.selectedKeys))

function isRowSelected(row, idx) {
  return selectedSet.value.has(props.rowKey(row, idx))
}

const allSelected = computed(() =>
  props.rows && props.rows.length > 0 && rowKeys.value.every(k => selectedSet.value.has(k))
)
const someSelected = computed(() => {
  const sel = rowKeys.value.filter(k => selectedSet.value.has(k)).length
  return sel > 0 && sel < rowKeys.value.length
})

function toggleAll(e) {
  if (e.target.checked) {
    emit('update:selectedKeys', [...rowKeys.value])
  } else {
    emit('update:selectedKeys', [])
  }
}
function toggleRow(row, idx) {
  const key = props.rowKey(row, idx)
  const set = new Set(props.selectedKeys)
  if (set.has(key)) set.delete(key)
  else set.add(key)
  emit('update:selectedKeys', Array.from(set))
}
// 点击表头选择列容器（非 checkbox 本身）时切换全选
function onHeaderSelectClick(e) {
  if (e.target.type === 'checkbox') return
  if (allSelected.value) {
    emit('update:selectedKeys', [])
  } else {
    emit('update:selectedKeys', [...rowKeys.value])
  }
}
// 点击行选择列容器（非 checkbox 本身）时切换该行选中状态
function onRowSelectClick(row, idx, e) {
  if (e.target.type === 'checkbox') return
  toggleRow(row, idx)
}
</script>
<style scoped>
.col-select {
  width: 44px;
  text-align: center;
  white-space: nowrap;
  cursor: pointer;
}
.bt-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  vertical-align: middle;
}
</style>
