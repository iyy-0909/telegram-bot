export function createTableSearch({ defineComponent, h }, ElInput, Search) {
  return defineComponent({
    name: 'TableSearch',
    props: {
      modelValue: { type: String, default: '' },
      placeholder: { type: String, default: '搜索名称 / ID / 状态 / 备注' },
      label: { type: String, required: true },
      count: Number,
      total: Number,
      disabled: Boolean,
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () => h('div', { class: 'table-search' }, [
        h(ElInput, {
          modelValue: props.modelValue,
          'onUpdate:modelValue': value => emit('update:modelValue', value),
          'aria-label': props.label,
          placeholder: props.placeholder,
          prefixIcon: Search,
          clearable: true,
          disabled: props.disabled,
        }),
        props.count === undefined ? null : h('span', {
          class: 'table-search__count', role: 'status', 'aria-live': 'polite',
        }, props.modelValue.trim() && props.total !== undefined
          ? `${props.count} / ${props.total} 条` : `共 ${props.count} 条`),
      ])
    },
  })
}
