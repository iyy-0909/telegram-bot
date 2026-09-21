import { defineComponent, h } from "vue"
import { parseTelegramPreview } from "../utils/telegramPreview.js"

function renderNodes(nodes) {
  return nodes.map((node) => node.type === "text"
    ? node.text
    : h(node.tag, null, renderNodes(node.children)))
}

export default defineComponent({
  name: "TelegramTextPreview",
  props: { text: { type: String, default: "" } },
  setup(props) {
    return () => h("div", {
      class: "telegram-text-preview",
      role: "region",
      "aria-label": "排版预览",
      tabindex: 0,
    }, renderNodes(parseTelegramPreview(props.text)))
  },
})
