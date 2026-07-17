"""
WebIntelPro Enterprise X
CDN Fingerprints
"""

FINGERPRINTS = [

    {
        "name": "Cloudflare",
        "category": "cdn",

        "headers": [
            "cf-ray",
            "cloudflare",
            "cf-cache-status",
        ],

        "meta": [],
        "scripts": [],
        "inline": [],
        "dom": [],
        "cookies": [],
        "stylesheets": [],
    },

    {
        "name": "CloudFront",
        "category": "cdn",

        "headers": [
            "cloudfront",
            "x-amz-cf-id",
        ],

        "meta": [],
        "scripts": [],
        "inline": [],
        "dom": [],
        "cookies": [],
        "stylesheets": [],
    },

    {
        "name": "Fastly",
        "category": "cdn",

        "headers": [
            "fastly",
            "x-served-by",
        ],

        "meta": [],
        "scripts": [],
        "inline": [],
        "dom": [],
        "cookies": [],
        "stylesheets": [],
    },

    {
        "name": "Akamai",
        "category": "cdn",

        "headers": [
            "akamai",
            "akamaighost",
        ],

        "meta": [],
        "scripts": [],
        "inline": [],
        "dom": [],
        "cookies": [],
        "stylesheets": [],
    },

]