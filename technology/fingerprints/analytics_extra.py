"""WebIntelPro Enterprise X - Additional Analytics / Monitoring Fingerprints"""

def _fp(name, scripts=(), inline=(), cookies=(), headers=()):
    return {"name": name, "category": "analytics", "headers": list(headers),
            "meta": [], "scripts": list(scripts), "inline": list(inline),
            "dom": [], "cookies": list(cookies)}

FINGERPRINTS = [
    _fp("Plausible", ["plausible.io/js"], ["plausible("]),
    _fp("Matomo", ["matomo.js", "piwik.js", "matomo.php"], ["_paq", "matomo"]),
    _fp("Fathom", ["cdn.usefathom.com"], ["fathom.trackpageview"]),
    _fp("Cloudflare Web Analytics", ["static.cloudflareinsights.com"], ["beacon.min.js"]),
    _fp("Amplitude", ["amplitude.js", "cdn.amplitude.com"], ["amplitude.getinstance"]),
    _fp("Heap", ["cdn.heapanalytics.com", "heap.js"], ["heap.load"]),
    _fp("FullStory", ["fullstory.com/s/fs.js", "edge.fullstory.com"], ["window['_fs_"]),
    _fp("Microsoft Clarity", ["clarity.ms/tag"], ["clarity(", "(c,l,a,r,i,t,y)"]),
    _fp("Yandex Metrica", ["mc.yandex.ru/metrika"], ["ym(", "yandex_metrika"]),
    _fp("Adobe Analytics", ["omniture", "s_code.js", "appmeasurement"], ["s.t(", "adobe analytics"]),
    _fp("PostHog", ["posthog", "app.posthog.com"], ["posthog.init"]),
    _fp("Snowplow", ["sp.js", "snowplow"], ["snowplow("]),
    _fp("Chartbeat", ["chartbeat.js", "static.chartbeat.com"], ["_sf_async_config"]),
    _fp("Quantcast", ["quantserve.com", "quantcast.mgr"], ["_qevents"]),
    _fp("New Relic", ["js-agent.newrelic.com", "nr-data.net"], ["nrewritecall", "newrelic"]),
    _fp("Sentry", ["browser.sentry-cdn.com", "sentry-cdn"], ["sentry.init", "__sentry__"]),
    _fp("Datadog RUM", ["datadoghq-browser-agent", "datadog-rum"], ["dd_rum", "datadogrum"]),
    _fp("LogRocket", ["cdn.logrocket.io", "logrocket"], ["logrocket.init"]),
    _fp("Crazy Egg", ["script.crazyegg.com"], ["ce_ready"]),
    _fp("Mouseflow", ["cdn.mouseflow.com"], ["_mfq"]),
    _fp("VWO", ["dev.visualwebsiteoptimizer.com", "vwo.com"], ["_vwo_code", "vwo"]),
]
