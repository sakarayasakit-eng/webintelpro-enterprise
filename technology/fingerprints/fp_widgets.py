"""WebIntelPro Enterprise X - Widgets & embeds (new categories)."""
def w(name, cat, scripts=(), inline=(), dom=()):
    return {"name": name, "category": cat, "headers": [], "meta": [],
            "scripts": list(scripts), "inline": list(inline), "dom": list(dom), "cookies": []}
FINGERPRINTS = [
    # search
    w("Algolia", "search", ["cdn.jsdelivr.net/npm/algoliasearch", "algolia.net"], ["algoliasearch(", "instantsearch("]),
    w("Elasticsearch UI", "search", ["searchkit"], ["searchkit"]),
    w("Coveo", "search", ["static.cloud.coveo.com"], ["coveo"]),
    w("Swiftype", "search", ["s.swiftypecdn.com"], ["swiftype"]),
    w("Klevu", "search", ["js.klevu.com"], ["klevu"]),
    # forms
    w("Typeform", "forms", ["embed.typeform.com"], ["typeform"], ["typeform-"]),
    w("Jotform", "forms", ["form.jotform.com", "cdn.jotfor.ms"], ["jotform"]),
    w("Google Forms", "forms", ["docs.google.com/forms"], []),
    w("Formspree", "forms", ["formspree.io"], ["formspree"]),
    w("Wufoo", "forms", ["wufoo.com/scripts"], ["wufoo"]),
    w("Calendly", "forms", ["assets.calendly.com"], ["calendly"], ["calendly-"]),
    # video / media
    w("Brightcove", "media", ["players.brightcove.net"], ["bc(", "brightcove"]),
    w("JW Player", "media", ["cdn.jwplayer.com", "jwpsrv.com"], ["jwplayer("]),
    w("Vidyard", "media", ["play.vidyard.com"], ["vidyard"]),
    w("Loom", "media", ["cdn.loom.com"], ["loomembedsdk"]),
    # maps
    w("Mapbox", "maps", ["api.mapbox.com"], ["mapboxgl", "l.mapbox"]),
    w("OpenStreetMap", "maps", ["tile.openstreetmap.org"], []),
    w("HERE Maps", "maps", ["js.api.here.com"], ["h.map"]),
    w("Google Maps Embed", "maps", ["maps.google.com/maps", "google.com/maps/embed"], []),
    # consent / privacy
    w("Cookie Consent (Osano)", "privacy", ["cookieconsent"], ["cookieconsent.initialise"]),
    w("Termly", "privacy", ["app.termly.io"], ["termly"]),
    w("TrustArc", "privacy", ["consent.trustarc.com"], ["truste"]),
    w("Quantcast Choice", "privacy", ["quantcast.mgr.consensu.org"], ["__cmp"]),
    w("Didomi", "privacy", ["sdk.privacy-center.org"], ["didomi"]),
    w("CookieYes", "privacy", ["cdn-cookieyes.com"], ["cookieyes"]),
    # translation / accessibility
    w("Weglot", "i18n", ["cdn.weglot.com"], ["weglot.initialize"]),
    w("Localize", "i18n", ["global.localizecdn.com"], ["localize"]),
    w("Transifex Live", "i18n", ["cdn.transifex.com/live.js"], ["txlive"]),
    w("Google Website Translator", "i18n", ["translate.google.com/translate_a"], ["google.translate"]),
    w("accessiBe", "accessibility", ["acsbapp.com", "accessibe.com"], ["acsbjs", "accessibe"]),
    w("UserWay", "accessibility", ["cdn.userway.org"], ["userway"]),
    w("AudioEye", "accessibility", ["ws.audioeye.com"], ["audioeye"]),
    # support / feedback / scheduling
    w("Zendesk Widget", "support", ["static.zdassets.com/ekr"], ["zendesk", "zesettings"]),
    w("Helpscout Beacon", "support", ["beacon-v2.helpscout.net"], ["beacon("]),
    w("Front Chat", "support", ["chat.frontapp.com"], ["frontchat"]),
    w("Kustomer", "support", ["cdn.kustomerapp.com"], ["kustomer"]),
    w("Delighted", "support", ["disc.delighted.com"], ["delighted"]),
    w("Hotjar Feedback", "support", ["static.hotjar.com/c/hotjar-feedback"], ["hjfeedback"]),
    w("Canny", "support", ["canny.io/sdk.js"], ["canny("]),
    w("Featurebase", "support", ["do.featurebase.app"], ["featurebase"]),
    # social embeds
    w("Instagram Embed", "social", ["platform.instagram.com/en_US/embeds.js"], ["instgrm"]),
    w("Twitter Embed", "social", ["platform.twitter.com/widgets.js"], ["twttr"]),
    w("Facebook SDK", "social", ["connect.facebook.net/en_us/sdk.js"], ["fb.init"], ["fb-root"]),
    w("YouTube IFrame API", "social", ["youtube.com/iframe_api"], ["yt.player"]),
]
