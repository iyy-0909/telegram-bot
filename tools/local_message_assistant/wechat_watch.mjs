/**
 * READ-ONLY diagnostic collector for the documented Computer Use sky API.
 * Run inside node_repl with an injected sky object. Does not start itself.
 * Candidate unread changes are NOT verified incoming private messages.
 * No friend acceptance, typing, sending, model calls or Codex task wakeups.
 */

export function parseSessions(tree) {
  const sessions = new Map();
  for (const line of tree.split('\n')) {
    const match = line.match(/^\s*\d+ 列表项目 .*? ID: session_item_(.+)$/);
    if (!match) continue;
    const name = match[1];
    const label = line.replace(/^\s*\d+ 列表项目 (?:\(selectable\) )?/, '').split(' ID: session_item_')[0];
    const count = label.match(/\[(\d+)条\]/);
    const previous = sessions.get(name);
    if (previous) {
      // Display names are not unique identities. Do not act on collisions.
      previous.ambiguous = true;
      continue;
    }
    sessions.set(name, {name, unread: count ? Number(count[1]) : 0, label, ambiguous: false});
  }
  return sessions;
}

export function changedUnread(before, after) {
  const changed = [];
  for (const [name, row] of after) {
    const old = before.get(name);
    // Newly visible rows may be old, unread conversations that merely scrolled into view.
    if (!old || row.ambiguous || old.ambiguous || row.unread <= 0) continue;
    if (row.unread > old.unread || (row.unread === old.unread && row.label !== old.label)) {
      changed.push({name, unread: row.unread, requiresPrivateVerification: true});
    }
  }
  return changed;
}

export function selectedGroup(tree) {
  const count = tree.match(/文本 \(\d+\) ID: .*\.current_chat_count_label/);
  const name = tree.match(/文本 (.+) ID: .*\.current_chat_name_label/);
  return count && name ? name[1] : null;
}

export async function sampleWindows(sky, returnedWindows) {
  const samples = [];
  for (const window of returnedWindows) {
    const state = await sky.get_window_state({window, include_screenshot: false, include_text: true});
    const tree = state.accessibility?.tree || '';
    if (!tree.includes('ID: session_list') || tree.includes('ID: login_layout_')) continue;
    samples.push({window: state.window, sessions: parseSessions(tree), group: selectedGroup(tree)});
  }
  return samples;
}
