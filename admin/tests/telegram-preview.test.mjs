import assert from "node:assert/strict"
import test from "node:test"
import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import TelegramTextPreview from "../src/components/TelegramTextPreview.js"
import { parseTelegramPreview } from "../src/utils/telegramPreview.js"

async function render(text) {
  return renderToString(createSSRApp({ render: () => h(TelegramTextPreview, { text }) }))
}

test("renders Telegram formatting, emoji, entities, and line breaks", async () => {
  const html = await render('<b>场所名称</b>\n\n💰 <strong>消费明细</strong>\n▫️500/600 &amp; 1290\n<i>地址</i><br><u>预约</u><s>旧信息</s>')
  assert.match(html, /<strong>场所名称<\/strong>\n\n💰 <strong>消费明细<\/strong>/)
  assert.match(html, /▫️500\/600 &amp; 1290\n<em>地址<\/em>\n<u>预约<\/u><s>旧信息<\/s>/)
  assert.match(html, /aria-label="排版预览"/)
})

test("drops event handlers, styles, URLs, and elements that could load resources", async () => {
  const html = await render('<b onclick="alert(1)" style="background:url(https://bad.test)">标题</b><img src="https://bad.test/image" onerror="alert(2)"><iframe src="https://bad.test">框架</iframe><svg><script>alert(3)</script></svg><a href="javascript:alert(4)">联系</a><a href="https://t.me/example" target="_blank">TG</a>')
  assert.match(html, /<strong>标题<\/strong><span>联系<\/span><span>TG<\/span>/)
  assert.doesNotMatch(html, /onclick|onerror|style=|src=|href=|target=|https:|javascript:|<img|<iframe|<svg|<script|alert\(/)
})

test("encoded markup remains plain text and is never parsed a second time", async () => {
  const html = await render('&lt;img src=x onerror=alert(1)&gt; &#x3c;script&#62;evil&lt;/script&gt; &amp;lt;b&amp;gt;')
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/)
  assert.match(html, /&lt;script&gt;evil&lt;\/script&gt;/)
  assert.match(html, /&amp;lt;b&amp;gt;/)
  assert.doesNotMatch(html, /<img|<script/)
})

test("malformed and unknown markup cannot produce executable nodes", async () => {
  const html = await render('<unknown onmouseover="alert(1)">正文</unknown><b title="> <img src=x>">加粗</b></i><!--hidden--><script>hidden')
  assert.match(html, /正文<strong>/)
  assert.match(html, /加粗<\/strong>/)
  assert.doesNotMatch(html, /onmouseover|title=|<unknown|<img|<script|hidden/)
})

test("invalid entities and deeply nested markup remain safe and bounded", async () => {
  const source = '<b>'.repeat(2000) + '内容 &#x110000; &#0; &#xd800; &#128512;' + '</b>'.repeat(2000)
  const html = await render(source)
  assert.equal((html.match(/<strong>/g) || []).length, 32)
  assert.match(html, /内容 � � � 😀/)
  assert.deepEqual(parseTelegramPreview(null), [])
})
