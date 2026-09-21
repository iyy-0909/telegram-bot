import test from 'node:test'
import assert from 'node:assert/strict'
import { createActionRunner, useRequestEmit, createRequestButton, createRequestSwitch } from '../../frontend-shared/requestActions.mjs'
import { defineComponent, h, ref, nextTick } from 'vue'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('a second click in the same tick does not start another request', async () => {
  const request = deferred(), states = []
  const runner = createActionRunner(value => states.push(value))
  let calls = 0
  const work = () => { calls++; return request.promise }
  const first = runner.run(work)
  runner.run(work)
  assert.equal(calls, 1)
  assert.equal(runner.pending, true)
  request.resolve()
  await first
  assert.equal(runner.pending, false)
  assert.deepEqual(states, [true, false])
  await runner.run(work)
  assert.equal(calls, 2)
})

test('validation and confirmation are part of the protected action', async () => {
  const confirmation = deferred(), network = deferred()
  const runner = createActionRunner()
  let requests = 0
  const action = async () => { await confirmation.promise; requests++; await network.promise }
  const first = runner.run(action)
  runner.run(action)
  confirmation.resolve()
  await Promise.resolve()
  runner.run(action)
  assert.equal(requests, 1)
  network.resolve()
  await first
  assert.equal(runner.pending, false)
})

test('rejection, cancellation and synchronous errors all release the lock', async () => {
  const runner = createActionRunner()
  for (const error of [new Error('offline'), 'cancel', 'close']) {
    await assert.rejects(runner.run(() => Promise.reject(error)), e => e === error)
    assert.equal(runner.pending, false)
  }
  assert.throws(() => runner.run(() => { throw Error('sync') }), /sync/)
  assert.equal(runner.pending, false)
  assert.equal(runner.run(() => 42), 42)
})

test('local actions stay synchronous without a loading flash', () => {
  const states = [], runner = createActionRunner(value => states.push(value))
  assert.equal(runner.run(() => 'opened'), 'opened')
  assert.ok(!states.includes(true))
})

test('callbacks propagate completion through nested components and preserve model events', async () => {
  const request = deferred(), events = []
  const parent = useRequestEmit(() => {}, { requestActions: { save: () => request.promise } })
  const child = useRequestEmit((...args) => events.push(args), { requestActions: { submit: payload => parent('save', payload) } })
  const runner = createActionRunner()
  const action = runner.run(() => child('submit', { name: 'example' }))
  child('update:visible', false)
  assert.deepEqual(events, [['update:visible', false]])
  assert.equal(runner.pending, true)
  request.resolve('saved')
  assert.equal(await action, 'saved')
  assert.equal(runner.pending, false)
})

test('duplicate row actions share completion while other rows remain independent', async () => {
  const request = deferred(), calls = []
  const emit = useRequestEmit(() => {}, { requestActions: { test: row => { calls.push(row.id); return request.promise } } })
  const first = emit('test', { id: 1 })
  const duplicate = emit('test', { id: 1 })
  const other = emit('test', { id: 2 })
  assert.equal(first, duplicate)
  assert.deepEqual(calls, [1, 2])
  request.resolve()
  await Promise.all([first, duplicate, other])
  await emit('test', { id: 1 })
  assert.deepEqual(calls, [1, 2, 1])
})

test('button exposes loading and disabled until completion and preserves attributes', async () => {
  const request = deferred(), errors = []
  const Button = createRequestButton({ defineComponent, h, ref }, 'fake-element-button', e => errors.push(e))
  let calls = 0
  const props = { onClick: () => { calls++; return request.promise }, disabled: false, loading: false }
  const render = Button.setup(props, { attrs: { 'aria-label': '刷新', class: 'existing' }, slots: {}, expose() {} })
  render().props.onClick({})
  render().props.onClick({ preventDefault() {}, stopImmediatePropagation() {} })
  assert.equal(calls, 1)
  assert.equal(render().props.loading, true)
  assert.equal(render().props.disabled, true)
  assert.equal(render().props['aria-busy'], true)
  assert.equal(render().props['aria-label'], '刷新')
  assert.equal(render().props.class, 'existing')
  request.reject(Error('offline'))
  await new Promise(resolve => setImmediate(resolve))
  await nextTick()
  assert.equal(render().props.loading, false)
  assert.equal(render().props.disabled, false)
  assert.deepEqual(errors, ['offline'])
})

test('disabled and externally loading buttons cannot call the action', () => {
  const Button = createRequestButton({ defineComponent, h, ref }, 'button', () => {})
  let calls = 0
  for (const state of [{ disabled: true }, { loading: true }]) {
    const render = Button.setup({ ...state, onClick: () => calls++ }, { attrs: {}, slots: {}, expose() {} })
    render().props.onClick({ preventDefault() {}, stopImmediatePropagation() {} })
  }
  assert.equal(calls, 0)
})

test('mobile actions distinguish records after a resource-type argument', async () => {
  const request = deferred(), ids = []
  const emit = useRequestEmit(() => {}, { requestActions: { delete: (type, row) => { ids.push(`${type}:${row.id}`); return request.promise } } })
  const first = emit('delete', 'bot', { id: 1 })
  const second = emit('delete', 'bot', { id: 2 })
  assert.deepEqual(ids, ['bot:1', 'bot:2'])
  request.resolve()
  await Promise.all([first, second])
})

test('request switches block repeated model changes until settled', async () => {
  const request = deferred()
  const Switch = createRequestSwitch({ defineComponent, h, ref }, 'switch', () => {})
  let calls = 0
  const render = Switch.setup({ onChange: () => { calls++; return request.promise } }, { attrs: { modelValue: true }, slots: {} })
  assert.equal(render().props.beforeChange(), true)
  render().props.onChange(false)
  assert.equal(render().props.beforeChange(), false)
  assert.equal(render().props.loading, true)
  render().props.onChange(true)
  assert.equal(calls, 1)
  request.resolve()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(render().props.beforeChange(), true)
  assert.equal(render().props.loading, false)
})
