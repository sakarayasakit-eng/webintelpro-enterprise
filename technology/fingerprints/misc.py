"""WebIntelPro Enterprise X - PWA / Delivery / Miscellaneous Fingerprints"""

def _fp(name, category, headers=(), meta=(), scripts=(), inline=(), dom=()):
    return {"name": name, "category": category, "headers": list(headers),
            "meta": list(meta), "scripts": list(scripts), "inline": list(inline),
            "dom": list(dom), "cookies": []}

FINGERPRINTS = [
    _fp("Google AMP", "pwa", scripts=["cdn.ampproject.org", "ampproject.org"], dom=["amp-boilerplate", "⚡"]),
    _fp("Service Worker", "pwa", inline=["serviceworker.register", "navigator.serviceworker"]),
    _fp("Web App Manifest", "pwa", dom=["rel=\"manifest\"", "manifest.json"]),
    _fp("Cloudflare Rocket Loader", "optimization", scripts=["cloudflare.com/rocket"], inline=["rocket-loader", "data-cfasync"]),
    _fp("WP Rocket", "optimization", scripts=["wp-rocket", "cache/wp-rocket"], inline=["rocketlazyload"]),
    _fp("LazySizes", "optimization", scripts=["lazysizes.min.js", "lazysizes"], dom=["lazyload", "data-src"]),
    _fp("Cookiebot", "privacy", scripts=["consent.cookiebot.com"], inline=["cookiebot"]),
    _fp("OneTrust", "privacy", scripts=["cdn.cookielaw.org", "onetrust"], inline=["onetrust"]),
    _fp("Osano", "privacy", scripts=["osano.com/uhc", "cmp.osano.com"], inline=["osano"]),
    _fp("Usercentrics", "privacy", scripts=["app.usercentrics.eu"], inline=["usercentrics"]),
    _fp("Cloudflare Stream", "media", scripts=["videodelivery.net", "cloudflarestream.com"]),
    _fp("Vimeo", "media", scripts=["player.vimeo.com"], dom=["vimeo"]),
    _fp("YouTube Embed", "media", dom=["youtube.com/embed", "youtube-nocookie.com"]),
    _fp("Wistia", "media", scripts=["fast.wistia.com", "wistia.com"], inline=["wistia"]),
]
