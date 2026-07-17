"""WebIntelPro Enterprise X - Extra analytics / experimentation."""
def a(name, scripts=(), inline=(), cookies=()):
    return {"name": name, "category": "analytics", "headers": [], "meta": [],
            "scripts": list(scripts), "inline": list(inline), "dom": [], "cookies": list(cookies)}
FINGERPRINTS = [
    a("Pendo", ["cdn.pendo.io", "pendo.js"], ["pendo.initialize"]),
    a("Smartlook", ["rec.smartlook.com", "smartlook"], ["smartlook("]),
    a("Contentsquare", ["t.contentsquare.net", "contentsquare"], ["_uxa"]),
    a("Kissmetrics", ["scripts.kissmetrics.io", "kissmetrics"], ["_kmq"]),
    a("Woopra", ["static.woopra.com"], ["woopra.track"]),
    a("Countly", ["countly.min.js", "cdn.count.ly"], ["countly.init"]),
    a("GoSquared", ["cdn.gosquared.com"], ["_gs("]),
    a("Parse.ly", ["cdn.parsely.com/keys"], ["parsely"]),
    a("Adobe Target", ["at.js", "adobetarget", "tt.omtrdc.net"], ["adobe.target"]),
    a("Piwik PRO", ["piwik.pro", "ppms.js"], ["_paq"]),
    a("Split.io", ["cdn.split.io", "split.min.js"], ["splitfactory"]),
    a("LaunchDarkly", ["launchdarkly", "clientstream.launchdarkly"], ["ldclient"]),
    a("Statsig", ["cdn.statsig.com"], ["statsig.initialize"]),
    a("Google Optimize", ["optimize.google.com", "gtm.js?id=opt"], ["ga('require', 'gaoptimize')"]),
    a("AB Tasty", ["try.abtasty.com"], ["abtasty"]),
    a("Convert", ["cdn-3.convertexperiments.com"], ["convert."]),
    a("Bugsnag", ["d2wy8f7a9ursnm.cloudfront.net/bugsnag", "bugsnag.min.js"], ["bugsnag(", "bugsnagclient"]),
    a("Rollbar", ["cdn.rollbar.com", "rollbar.min.js"], ["rollbar."]),
    a("TrackJS", ["cdn.trackjs.com"], ["trackjs"]),
    a("Raygun", ["cdn.raygun.io"], ["rg4js("]),
]
