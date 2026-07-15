<template>
  <ArtSearchBar
    ref="searchBarRef"
    v-model="formData"
    :items="formItems"
    @reset="handleReset"
    @search="handleSearch"
  >
  </ArtSearchBar>
</template>

<script setup lang="ts">
  type UserSearchParams = Api.SystemManage.UserSearchParams

  interface Props {
    modelValue: UserSearchParams
  }

  interface Emits {
    (e: 'update:modelValue', value: UserSearchParams): void
    (e: 'search', params: UserSearchParams): void
    (e: 'reset'): void
  }

  const props = defineProps<Props>()
  const emit = defineEmits<Emits>()

  const searchBarRef = ref()

  const formData = computed({
    get: () => props.modelValue,
    set: (val) => emit('update:modelValue', val)
  })

  const statusOptions = [
    { label: '全部', value: '' },
    { label: '正常', value: '正常' },
    { label: '禁用', value: '禁用' }
  ]

  const formItems = computed(() => [
    {
      label: '关键词',
      key: 'username',
      type: 'input',
      placeholder: '用户名 / 昵称 / 手机号 / 邮箱',
      clearable: true
    },
    {
      label: '状态',
      key: 'status',
      type: 'select',
      props: {
        placeholder: '请选择状态',
        options: statusOptions,
        clearable: true
      }
    }
  ])

  function handleReset() {
    emit('reset')
  }

  async function handleSearch(params: UserSearchParams) {
    await searchBarRef.value?.validate()
    emit('search', params)
  }
</script>