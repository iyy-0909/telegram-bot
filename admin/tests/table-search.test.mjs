import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { matchesSearch, matchesRow, searchRows } from '../../frontend-shared/search.mjs'
import { createTableSearch } from '../../frontend-shared/tableSearch.mjs'

for (const [kind, row, keyword] of [
  ['accounts', { id: 73, name: '上海采集', username: '@Collector_73' }, 'https://t.me/collector_73'],
  ['accounts', { phone_masked: '138****9876' }, '9876'],
  ['bots', { username: '@distribution_demo', enabled: false }, '已停用'],
  ['support', { support_group_chat_id: '-100123456', welcome_message: '欢迎咨询' }, '咨询'],
  ['tasks', { target_channels: '["@channel_a", "@channel_b"]' }, 'https://t.me/channel_b'],
  ['tasks', { id: 912, status: 'stopped' }, '已停止'],
  ['events', { event_type: 'filtered', message: '命中关键词' }, '过滤'],
  ['queue', { source_type: 'listener_catchup' }, '监听补齐'],
  ['templates', { items: [{ content: '很长的内容'.repeat(100) + '最后的关键字' }] }, '最后的关键字'],
  ['templates', { type: 'footer' }, '底部'],
  ['searchBots', { remark: '人工审核', account_name: '上海运营' }, '上海运营'],
  ['submissions', { manual_account_id: '732456', review_status: 'reviewing' }, '审核中'],
  ['submissions', { submit_status: 'success' }, '已添加'],
  ['collections', { collectedLinks: ['https://t.me/test_channel'] }, '@TEST_CHANNEL'],
  ['channels', { creator_username: '@creator_demo', remark: '营业中' }, 'creator_demo'],
  ['notifications', { ntfy_url: 'telegram_demo', account_id: 9182 }, '9182'],
  ['bindings', { target_channel: '@target_demo' }, 'https://t.me/s/target_demo/123'],
  ['rules', { source: '@source_demo' }, 'source_demo'],
  ['bulk', { target_message_id: 8765, error_message: '权限不足' }, '权限不足'],
]) {
  test(`${kind}: ${keyword}`, () => assert.equal(matchesRow(row, keyword, kind), true))
}

test('does not search credentials or unmapped internal fields', () => {
  const row = { id: 1, name: '测试账号', token: 'private-token', password: 'private-pass', session_path: '/private-session' }
  for (const kind of ['accounts', 'bots', 'support', 'notifications']) {
    assert.equal(matchesRow(row, 'private', kind), false)
  }
})

test('reviewing, pending and collection results are distinct', () => {
  assert.equal(matchesRow({ review_status: 'pending' }, '审核中', 'submissions'), false)
  assert.equal(matchesRow({ collection_status: 'not_collected' }, '已收录', 'submissions'), false)
  assert.equal(matchesRow({ status: 'disabled' }, '正常', 'tasks'), false)
})

test('filtering preserves ordering, original rows and unsaved input', () => {
  const rows = [{ account_id: 1, ntfy_url: 'first' }, { account_id: 2, ntfy_url: 'draft_value' }]
  const filtered = searchRows(rows, 'draft', 'notifications')
  assert.deepEqual(filtered, [rows[1]])
  assert.equal(filtered[0], rows[1])
  filtered[0].ntfy_url = 'retained_draft'
  assert.equal(searchRows(rows, ' ', 'notifications'), rows)
  assert.equal(rows[1].ntfy_url, 'retained_draft')
  assert.deepEqual(searchRows(rows, 'no_match', 'notifications'), [])
})

test('search entire loaded list before rendering, including row 20', () => {
  const rows = Array.from({ length: 20 }, (_, i) => ({ task_id: i + 1, task_name: `任务 ${i + 1}` }))
  assert.equal(searchRows(rows, '任务 20', 'queue')[0].task_id, 20)
})

test('nulls, whitespace, case and Telegram links remain supported', () => {
  assert.equal(matchesSearch([null, undefined, '@Channel_Test'], '  HTTPS://T.ME/CHANNEL_TEST  '), true)
  assert.equal(matchesSearch([], '   '), true)
  assert.deepEqual(searchRows(undefined, 'missing', 'tasks'), [])
  assert.equal(matchesSearch(['@different'], 'https://t.me/+invite'), false)
})

test('related display fields are searchable without leaking full objects', () => {
  assert.equal(matchesRow({ bot_id: 1 }, '机器人名称', 'bindings', ['机器人名称']), true)
})

test('desktop and mobile export the same matcher', async () => {
  const desktop = await import('../src/utils/search.js')
  const mobile = await import('../../admin-mobile/src/utils/search.js')
  assert.equal(desktop.matchesSearch, mobile.matchesSearch)
  assert.equal(desktop.searchRows, mobile.searchRows)
})

test('search control is clearable, labelled and emits only a filter change', () => {
  const emitted = []
  const component = createTableSearch({ defineComponent: x => x, h: (type, props, children) => ({ type, props, children }) }, 'input', 'search')
  const tree = component.setup({ modelValue: 'test', label: '搜索账号', count: 1, total: 20 }, { emit: (...args) => emitted.push(args) })()
  const input = tree.children[0]
  assert.equal(input.props['aria-label'], '搜索账号')
  assert.equal(input.props.clearable, true)
  input.props['onUpdate:modelValue']('')
  assert.deepEqual(emitted, [['update:modelValue', '']])
  assert.equal(tree.children[1].children, '1 / 20 条')
})

test('all desktop data tables use a searched or server-filtered data source', () => {
  const directory = new URL('../src/components/', import.meta.url)
  let tableCount = 0
  for (const file of readdirSync(directory).filter(name => name.endsWith('.vue'))) {
    const source = readFileSync(new URL(file, directory), 'utf8')
    for (const [, attributes] of source.matchAll(/<el-table(?=[\s>])([^>]+)>/g)) {
      tableCount++
      assert.match(attributes, /:data="(?:filtered\w*|visible\w*|runtimeEvents|alerts|pagedUsers)"/, file)
    }
  }
  assert.equal(tableCount, 27)
})
