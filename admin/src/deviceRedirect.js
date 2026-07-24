const MOBILE_USER_AGENT = /Android|iPhone|iPod|IEMobile|Mobile|Opera Mini/i

export function shouldUseMobileSite({
  location = window.location,
  navigator = window.navigator,
  matchMedia = window.matchMedia.bind(window),
} = {}) {
  const params = new URLSearchParams(location.search)
  if (params.get("desktop") === "1") return false
  if (params.get("mobile") === "1") return true

  const mobileUserAgent = MOBILE_USER_AGENT.test(navigator.userAgent || "")
  const compactTouchScreen =
    matchMedia("(max-width: 767px)").matches &&
    matchMedia("(pointer: coarse)").matches

  return mobileUserAgent || compactTouchScreen
}

export function redirectToMobileSite() {
  if (window.location.pathname.startsWith("/mobile/")) return false
  if (!shouldUseMobileSite()) return false

  const target = new URL(window.location.href)
  const isLocalDesktopDev =
    ["localhost", "127.0.0.1"].includes(target.hostname) &&
    target.port === "5173"

  target.searchParams.delete("mobile")
  if (isLocalDesktopDev) {
    target.port = "5174"
    target.pathname = "/mobile/"
  } else {
    target.pathname = "/mobile/"
  }

  window.location.replace(target.toString())
  return true
}
