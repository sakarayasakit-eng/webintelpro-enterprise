"""WebIntelPro Enterprise X - Additional Hosting Provider Fingerprints"""

def _fp(name, headers=(), scripts=(), inline=()):
    return {"name": name, "category": "hosting", "headers": list(headers),
            "meta": [], "scripts": list(scripts), "inline": list(inline),
            "dom": [], "cookies": []}

FINGERPRINTS = [
    _fp("Fly.io", headers=["fly-request-id", "server:fly"]),
    _fp("Railway", headers=["x-railway", "railway"]),
    _fp("Firebase Hosting", headers=["x-served-by:firebase"], scripts=["firebaseapp.com", "firebasejs"], inline=["firebase.initializeapp"]),
    _fp("Surge", headers=["server:surge"]),
    _fp("Cloudflare Workers", headers=["cf-worker"]),
    _fp("AWS Amplify", headers=["x-amz-cf-pop"], scripts=["amplifyapp.com"]),
    _fp("WP Engine", headers=["x-wpengine", "wpengine"]),
    _fp("Kinsta", headers=["x-kinsta-cache", "kinsta"]),
    _fp("SiteGround", headers=["x-siteground", "siteground"]),
    _fp("Pantheon", headers=["x-pantheon", "pantheon"]),
    _fp("GoDaddy", headers=["godaddy"]),
    _fp("Squarespace Hosting", headers=["server:squarespace"]),
    _fp("Fastly Hosting", headers=["x-fastly"]),
    _fp("Render Hosting", headers=["x-render"]),
]
