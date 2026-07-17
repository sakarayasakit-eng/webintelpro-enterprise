"""
WebIntelPro Enterprise X
Analytics Fingerprints
"""

FINGERPRINTS = [

    {
        "name": "Google Analytics 4",
        "category": "analytics",

        "headers": [],
        "meta": [],

        "scripts": [
            "googletagmanager.com/gtag",
            "gtag/js",
        ],

        "inline": [
            "gtag(",
        ],

        "dom": [],

        "cookies": [
            "_ga",
            "_gid",
        ],
    },

    {
        "name": "Google Tag Manager",
        "category": "analytics",

        "headers": [],
        "meta": [],

        "scripts": [
            "googletagmanager.com",
        ],

        "inline": [
            "dataLayer",
            "gtm.js",
        ],

        "dom": [],

        "cookies": [],

        # GTM is often injected by a dynamic loader, so googletagmanager.com
        # never appears as a <script src>. These tokens are GTM-specific (GA4
        # uses gtag/js, never a GTM- container id or ns.html), so keying them
        # on the raw HTML catches dynamic installs without GA4 false positives.
        "html": [
            "googletagmanager.com/gtm.js",
            "googletagmanager.com/ns.html",
            "gtm-",
        ],
    },

    {
        "name": "Hotjar",
        "category": "analytics",

        "headers": [],
        "meta": [],

        "scripts": [
            "hotjar",
        ],

        "inline": [
            "hj(",
            "_hjSettings",
        ],

        "dom": [],

        "cookies": [
            "_hjSession",
        ],
    },

    {
        "name": "Mixpanel",
        "category": "analytics",

        "headers": [],
        "meta": [],

        "scripts": [
            "mixpanel",
        ],

        "inline": [
            "mixpanel.init",
        ],

        "dom": [],

        "cookies": [],
    },

]