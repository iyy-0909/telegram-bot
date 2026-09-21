// Parse only presentation tags. Never create a browser HTML document from AI output:
// even detached HTML documents may load external images or other resources.
const TAGS = new Map([
  ["b", "strong"], ["strong", "strong"],
  ["i", "em"], ["em", "em"],
  ["u", "u"], ["ins", "u"],
  ["s", "s"], ["strike", "s"], ["del", "s"],
  ["code", "code"], ["pre", "pre"], ["blockquote", "blockquote"],
  ["a", "span"], ["span", "span"], ["tg-spoiler", "span"], ["tg-emoji", "span"],
])
const HIDDEN_TAGS = new Set(["script", "style", "iframe", "object", "embed", "svg", "math", "template"])
const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0" }
const MAX_DEPTH = 32

function decodeText(value) {
  return value.replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (whole, entity) => {
    if (!entity.startsWith("#")) return ENTITIES[entity.toLowerCase()] ?? whole
    const hexadecimal = entity[1].toLowerCase() === "x"
    const codePoint = Number.parseInt(entity.slice(hexadecimal ? 2 : 1), hexadecimal ? 16 : 10)
    if (!Number.isFinite(codePoint) || codePoint <= 0 || codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) return "\ufffd"
    return String.fromCodePoint(codePoint)
  })
}

/** Safe display tree; source attributes and URLs are deliberately never returned. */
export function parseTelegramPreview(value) {
  const source = String(value ?? "")
  const root = { children: [] }
  const stack = [{ sourceTag: "", node: root }]
  const tokens = /<!--[\s\S]*?(?:-->|$)|<\/?[A-Za-z][^>]*>/g
  let hiddenTag = ""
  let hiddenDepth = 0
  let offset = 0

  function appendText(value) {
    if (!value || hiddenTag) return
    const children = stack[stack.length - 1].node.children
    const text = decodeText(value)
    const previous = children[children.length - 1]
    if (previous?.type === "text") previous.text += text
    else children.push({ type: "text", text })
  }

  for (const match of source.matchAll(tokens)) {
    appendText(source.slice(offset, match.index))
    offset = match.index + match[0].length
    const tagMatch = /^<(\/?)([A-Za-z][\w-]*)\b/.exec(match[0])
    if (!tagMatch) continue
    const closing = Boolean(tagMatch[1])
    const sourceTag = tagMatch[2].toLowerCase()
    const selfClosing = /\/\s*>$/.test(match[0])
    if (hiddenTag) {
      if (sourceTag === hiddenTag) {
        if (closing) hiddenDepth -= 1
        else if (!selfClosing) hiddenDepth += 1
        if (hiddenDepth === 0) hiddenTag = ""
      }
      continue
    }
    if (HIDDEN_TAGS.has(sourceTag)) {
      if (!closing && !selfClosing && sourceTag !== "embed") {
        hiddenTag = sourceTag
        hiddenDepth = 1
      }
      continue
    }
    if (sourceTag === "br") {
      if (!closing) appendText("\n")
      continue
    }
    const tag = TAGS.get(sourceTag)
    if (!tag) continue
    if (closing) {
      const index = stack.findLastIndex((entry) => entry.sourceTag === sourceTag)
      if (index > 0) stack.length = index
    } else if (stack.length <= MAX_DEPTH) {
      const node = { type: "element", tag, children: [] }
      stack[stack.length - 1].node.children.push(node)
      if (!selfClosing) stack.push({ sourceTag, node })
    }
  }
  appendText(source.slice(offset))
  return root.children
}
