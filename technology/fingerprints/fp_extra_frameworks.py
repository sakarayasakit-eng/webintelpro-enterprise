"""WebIntelPro Enterprise X - Extra frameworks (frontend/backend)."""
def f(name, headers=(), scripts=(), inline=(), dom=(), cookies=()):
    return {"name": name, "category": "framework", "headers": list(headers), "meta": [],
            "scripts": list(scripts), "inline": list(inline), "dom": list(dom), "cookies": list(cookies)}
FINGERPRINTS = [
    f("Blazor", scripts=["_framework/blazor", "blazor.webassembly.js"], inline=["blazor.start"], dom=["_bl_"]),
    f("SolidStart", scripts=["/_build/", "solid-start"], inline=["_$hydrationkey"]),
    f("Fresh (Deno)", scripts=["/_frsh/"], inline=["__fresh"]),
    f("Inertia.js", scripts=["@inertiajs"], inline=["inertia"]),
    f("Livewire", scripts=["livewire.js", "@livewire"], inline=["window.livewire"], dom=["wire:id"]),
    f("Phoenix LiveView", scripts=["phoenix_live_view", "phoenix.js"], inline=["livesocket"], dom=["phx-"]),
    f("FastAPI", headers=["x-fastapi"], scripts=["/openapi.json"], inline=["swagger-ui"]),
    f("Play Framework", headers=["x-play"], cookies=["play_session"]),
    f("Struts", scripts=[".action", "/struts/"], cookies=["jsessionid"]),
    f("Vaadin", scripts=["vaadin", "/vaadinservlet"], inline=["vaadin"], dom=["vaadin-"]),
    f("Blitz.js", scripts=["blitz"], inline=["__blitz"]),
    f("RedwoodJS", scripts=["redwoodjs", "/static/js/runtime"], inline=["__redwood__"]),
    f("AdonisJS", headers=["x-adonis"], cookies=["adonis-session"]),
    f("NestJS", headers=["x-powered-by:nest"], inline=["nestfactory"]),
]
