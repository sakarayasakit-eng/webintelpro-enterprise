"""WebIntelPro Enterprise X - Extra marketing / ads / social / email / reviews."""
def m(name, cat, scripts=(), inline=(), dom=(), cookies=()):
    return {"name": name, "category": cat, "headers": [], "meta": [],
            "scripts": list(scripts), "inline": list(inline), "dom": list(dom), "cookies": list(cookies)}
FINGERPRINTS = [
    m("TikTok Pixel", "marketing", ["analytics.tiktok.com"], ["ttq.load", "ttq.track"]),
    m("Pinterest Tag", "marketing", ["s.pinimg.com/ct"], ["pintrk("]),
    m("Snap Pixel", "marketing", ["sc-static.net/scevent"], ["snaptr("]),
    m("Reddit Pixel", "marketing", ["www.redditstatic.com/ads"], ["rdt("]),
    m("Quora Pixel", "marketing", ["a.quora.com/qevents.js"], ["qp("]),
    m("Bing Ads UET", "marketing", ["bat.bing.com/bat.js"], ["uetq"]),
    m("Taboola", "marketing", ["cdn.taboola.com"], ["_taboola"]),
    m("Outbrain", "marketing", ["widgets.outbrain.com"], ["obapi"]),
    m("Criteo", "marketing", ["static.criteo.net"], ["criteo_q"]),
    m("AdRoll", "marketing", ["s.adroll.com"], ["adroll_adv_id", "__adroll"]),
    m("Sendinblue", "marketing", ["sibautomation.com", "sendinblue"], ["sib_"]),
    m("Omnisend", "marketing", ["omnisrc.com", "omnisend"], ["omnisend"]),
    m("Drip", "marketing", ["tag.getdrip.com"], ["_dcq", "drip"]),
    m("ConvertKit", "marketing", ["f.convertkit.com", "convertkit"], [], ["formkit-form"]),
    m("Yotpo Reviews", "marketing", ["staticw2.yotpo.com"], ["yotpo"], ["yotpo"]),
    m("Trustpilot", "marketing", ["widget.trustpilot.com"], ["trustpilot"], ["trustpilot-widget"]),
    m("Bazaarvoice", "marketing", ["apps.bazaarvoice.com"], ["bvseo", "bvapi"]),
    m("Judge.me", "marketing", ["cdn.judge.me"], ["judgeme"], ["jdgm-"]),
    m("AddThis", "marketing", ["s7.addthis.com"], ["addthis"], ["addthis_toolbox"]),
    m("ShareThis", "marketing", ["platform-api.sharethis.com"], ["sharethis"], ["sharethis-"]),
    m("Disqus", "marketing", ["disqus.com/embed.js", ".disqus.com"], ["disqus_"], ["disqus_thread"]),
    m("Hello Bar", "marketing", ["my.hellobar.com"], ["hellobar"]),
]
