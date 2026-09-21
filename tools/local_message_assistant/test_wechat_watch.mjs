import assert from 'node:assert/strict';
import {parseSessions, changedUnread, selectedGroup} from './wechat_watch.mjs';

const tree = (count, text='你好') => `10 列表项目 (selectable) 客户 [${count}条] ${text} 12:00 ID: session_item_客户`;
assert.deepEqual(changedUnread(parseSessions(tree(1)), parseSessions(tree(1))), []);
assert.equal(changedUnread(parseSessions(tree(1)), parseSessions(tree(2))).length, 1);
assert.deepEqual(changedUnread(new Map(), parseSessions(tree(2))), []);
assert.deepEqual(changedUnread(parseSessions(tree(2)), parseSessions(tree(1))), []);
assert.equal(changedUnread(parseSessions(tree(1)), parseSessions(tree(1, '位置在哪'))).length, 1);
assert.deepEqual(changedUnread(parseSessions(tree(1)), parseSessions(tree(2)+'\n'+tree(3))), []);
assert.equal(selectedGroup('文本 测试群 ID: header.current_chat_name_label\n文本 (20) ID: header.current_chat_count_label'), '测试群');
assert.equal(selectedGroup('文本 客户 ID: header.current_chat_name_label'), null);
console.log('8 WeChat collector checks passed');
