"""
WebIntelPro Enterprise X
CSS Framework Fingerprints
"""

FINGERPRINTS = [

    {
        "name": "Bootstrap",
        "category": "css",

        "headers": [],
        "meta": [],

        "scripts": [],

        "inline": [],

        "dom": [],

        "cookies": [],

        "stylesheets": [
            "bootstrap",
        ],
    },

    {
        # Definitive Tailwind signals (single match is enough):
        #  - a stylesheet literally named tailwind
        #  - the Tailwind Play CDN script used by prototypes
        "name": "Tailwind CSS",
        "category": "css",

        "headers": [],
        "meta": [],

        "scripts": [
            "cdn.tailwindcss.com",
        ],

        "inline": [],

        "dom": [],

        "cookies": [],

        "stylesheets": [
            "tailwind",
        ],
    },

    {
        # Heuristic Tailwind signal for compiled/purged builds: the class name
        # is gone from the hashed stylesheet and --tw-* lives in the CSS we
        # don't fetch, so only utility classes survive in the HTML. The
        # variant-prefixed `variant:` colon syntax is highly Tailwind-specific;
        # min_evidence requires >=2 distinct ones so a stray class can't
        # false-trigger a detection.
        "name": "Tailwind CSS",
        "category": "css",

        "headers": [],
        "meta": [],
        "scripts": [],
        "inline": [],
        "cookies": [],
        "stylesheets": [],

        "dom": [
            "group-hover:",
            "dark:bg-",
            "dark:text-",
            "md:flex",
            "lg:flex",
            "md:grid",
            "sm:px-",
            "sm:py-",
            "space-y-",
            "space-x-",
            "focus-visible:",
        ],

        "min_evidence": 2,
    },

    {
        "name": "Bulma",
        "category": "css",

        "headers": [],
        "meta": [],

        "scripts": [],

        "inline": [],

        "dom": [],

        "cookies": [],

        "stylesheets": [
            "bulma",
        ],
    },

    {
        "name": "Foundation",

        "category": "css",

        "headers": [],
        "meta": [],

        "scripts": [],

        "inline": [],

        "dom": [],

        "cookies": [],

        "stylesheets": [
            "foundation",
        ],
    },

]