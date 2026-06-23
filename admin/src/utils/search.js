export function buildSearchTerms(value) {
  const raw = String(value ?? "").trim().toLowerCase()

  if (!raw) {
    return []
  }

  const terms = new Set([raw])
  const telegramName = extractTelegramName(raw)

  if (telegramName) {
    terms.add(telegramName)
    terms.add(`@${telegramName}`)
    terms.add(`t.me/${telegramName}`)
    terms.add(`https://t.me/${telegramName}`)
  } else if (raw.startsWith("@") && raw.length > 1) {
    const name = raw.slice(1).trim()
    terms.add(name)
    terms.add(`t.me/${name}`)
    terms.add(`https://t.me/${name}`)
  } else if (/^[a-z0-9_]{4,}$/i.test(raw)) {
    terms.add(`@${raw}`)
    terms.add(`t.me/${raw}`)
    terms.add(`https://t.me/${raw}`)
  }

  return Array.from(terms).filter(Boolean)
}

export function matchesSearch(values, keyword) {
  const terms = buildSearchTerms(keyword)

  if (!terms.length) {
    return true
  }

  const haystack = values
    .flatMap((value) => normalizeValue(value))
    .join(" ")
    .toLowerCase()

  return terms.some((term) => haystack.includes(term))
}

function normalizeValue(value) {
  if (value === null || value === undefined) {
    return []
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => normalizeValue(item))
  }

  if (typeof value === "object") {
    return Object.values(value).flatMap((item) => normalizeValue(item))
  }

  const text = String(value)
  const terms = buildSearchTerms(text)
  return [text, ...terms]
}

function extractTelegramName(value) {
  const match = value.match(/(?:https?:\/\/)?(?:www\.)?(?:t\.me|telegram\.me)\/(?:s\/)?([^/?#\s]+)/i)

  if (!match) {
    return ""
  }

  const name = match[1].trim().replace(/^@/, "")

  if (!name || name.startsWith("+") || name === "c") {
    return ""
  }

  return name
}
