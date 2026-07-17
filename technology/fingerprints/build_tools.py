"""WebIntelPro Enterprise X - Build Tool / Bundler Fingerprints"""

def _fp(name, scripts=(), inline=(), dom=()):
    return {"name": name, "category": "build", "headers": [], "meta": [],
            "scripts": list(scripts), "inline": list(inline), "dom": list(dom),
            "cookies": []}

FINGERPRINTS = [
    _fp("Webpack", ["webpack", "/dist/", "chunk.js"], ["webpackjsonp", "__webpack_require__"]),
    _fp("Vite", ["/assets/index-", "@vite/client", "vite/dist"], ["import.meta.hot", "__vite__"]),
    _fp("Parcel", ["parcel", ".parcel"], ["parcelRequire"]),
    _fp("Rollup", ["rollup"], []),
    _fp("esbuild", ["esbuild"], []),
    _fp("Turbopack", ["turbopack"], ["__turbopack"]),
    _fp("Snowpack", ["snowpack", "_snowpack"], []),
    _fp("RequireJS", ["require.js", "requirejs"], ["requirejs.config", "define.amd"]),
    _fp("SystemJS", ["system.js", "systemjs"], ["system.import"]),
]
