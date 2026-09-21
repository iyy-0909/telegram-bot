// Action callbacks return their promise across component boundaries. Vue events
// remain available for model updates and notifications with no callback supplied.
export function useRequestEmit(emit, props) {
  const running = new Map()
  return (event, ...args) => {
    const action = props.requestActions?.[event]
    if (typeof action !== 'function') return emit(event, ...args)
    const target = args.map(value => value?.id ?? (
      typeof value === 'string' || typeof value === 'number' ? value : ''
    )).join(':')
    const key = `${event}:${target}`
    if (running.has(key)) return running.get(key)
    const result = action(...args)
    if (!result?.then) return result
    const promise = Promise.resolve(result).finally(() => running.delete(key))
    running.set(key, promise)
    return promise
  }
}

export function createRequestSwitch({ defineComponent, h, ref }, ElSwitch, reportError) {
  return defineComponent({
    name: 'RequestSwitch',
    inheritAttrs: false,
    props: { onChange: Function, loading: Boolean, disabled: Boolean },
    setup(props, { attrs, slots }) {
      const pending = ref(false)
      const runner = createActionRunner(value => { pending.value = value })
      function change(value) {
        try {
          const result = runner.run(() => props.onChange?.(value))
          result?.catch?.(handleError)
        } catch (error) { handleError(error) }
      }
      function handleError(error) {
        if (error === 'cancel' || error === 'close' || error?.code === 'ERR_CANCELED') return
        const detail = error?.response?.data?.detail
        reportError(typeof detail === 'string' ? detail : error?.message || '操作失败，请重试')
      }
      return () => h(ElSwitch, {
        ...attrs,
        loading: props.loading || pending.value,
        disabled: props.disabled || props.loading || pending.value,
        'aria-busy': props.loading || pending.value,
        // Block before Element Plus updates v-model, including same-tick clicks.
        beforeChange: () => !runner.pending && !props.loading && !props.disabled,
        onChange: change,
      }, slots)
    },
  })
}

export function createActionRunner(onPending = () => {}) {
  let pending = false
  return {
    get pending() { return pending },
    run(action) {
      if (pending) return
      // Lock synchronously: Vue's next render may not have disabled the DOM yet.
      pending = true
      const release = () => { pending = false; onPending(false) }
      try {
        const result = action()
        if (result && typeof result.then === 'function') {
          onPending(true)
          return Promise.resolve(result).finally(release)
        }
        release()
        return result
      } catch (error) {
        release()
        throw error
      }
    },
  }
}

export function createRequestButton({ defineComponent, h, ref }, ElButton, reportError) {
  return defineComponent({
    name: 'RequestButton',
    inheritAttrs: false,
    props: {
      onClick: [Function, Array],
      loading: Boolean,
      disabled: Boolean,
      // Used for existing native buttons whose classes must be preserved.
      native: Boolean,
    },
    setup(props, { attrs, slots, expose }) {
      const pending = ref(false)
      const button = ref(null)
      const runner = createActionRunner(value => { pending.value = value })
      function click(event) {
        if (props.disabled || props.loading || runner.pending) {
          event?.preventDefault()
          event?.stopImmediatePropagation()
          return
        }
        try {
          const result = runner.run(() => {
            if (!Array.isArray(props.onClick)) return props.onClick?.(event)
            const results = props.onClick.map(handler => handler(event))
            return results.some(value => value?.then) ? Promise.all(results) : undefined
          })
          result?.catch?.(handleError)
        } catch (error) { handleError(error) }
      }
      function handleError(error) {
        if (error === 'cancel' || error === 'close' || error?.code === 'ERR_CANCELED') return
        const detail = error?.response?.data?.detail
        reportError(typeof detail === 'string' ? detail : error?.message || '操作失败，请重试')
      }
      expose({ ref: button, focus: () => button.value?.focus?.() })
      return () => {
        const busy = props.loading || pending.value
        const common = { ...attrs, ref: button, disabled: props.disabled || busy, 'aria-busy': busy, onClick: click }
        if (props.native) {
          return h('button', { type: 'button', ...common }, [
            busy ? h('span', { class: 'request-button-spinner', 'aria-hidden': 'true' }) : null,
            slots.default?.(),
          ])
        }
        // Icon-only round controls have room for one icon; retain their label.
        const buttonSlots = busy && attrs.circle !== undefined && attrs.circle !== false
          ? { ...slots, default: undefined }
          : slots
        return h(ElButton, { ...common, loading: busy }, buttonSlots)
      }
    },
  })
}
