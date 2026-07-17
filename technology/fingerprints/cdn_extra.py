"""WebIntelPro Enterprise X - Additional CDN / Asset Host Fingerprints"""

def _fp(name, headers=(), scripts=(), stylesheets=()):
    return {"name": name, "category": "cdn", "headers": list(headers),
            "meta": [], "scripts": list(scripts), "inline": [], "dom": [],
            "cookies": [], "stylesheets": list(stylesheets)}

FINGERPRINTS = [
    _fp("jsDelivr", scripts=["cdn.jsdelivr.net"], stylesheets=["cdn.jsdelivr.net"]),
    _fp("unpkg", scripts=["unpkg.com"], stylesheets=["unpkg.com"]),
    _fp("cdnjs", scripts=["cdnjs.cloudflare.com"], stylesheets=["cdnjs.cloudflare.com"]),
    _fp("Google Hosted Libraries", scripts=["ajax.googleapis.com/ajax/libs"]),
    _fp("KeyCDN", headers=["keycdn"], scripts=["kxcdn.com"]),
    _fp("StackPath", headers=["stackpath"], scripts=["stackpathcdn.com"]),
    _fp("BunnyCDN", headers=["bunnycdn"], scripts=["b-cdn.net"]),
    _fp("Azure CDN", headers=["x-azure-ref"], scripts=["azureedge.net"]),
    _fp("Alibaba Cloud CDN", headers=["ali-cdn", "x-swift"]),
    _fp("Gcore", headers=["gcore"], scripts=["gcorelabs.com", "gcdn.co"]),
    _fp("CDN77", headers=["cdn77"], scripts=["cdn77.org"]),
    _fp("Imperva CDN", headers=["x-cdn:incapsula"]),
]
