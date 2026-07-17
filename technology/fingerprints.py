"""
WebIntelPro Enterprise X
Technology Fingerprint Database (Version 2)

Enterprise rule-based fingerprint engine.
"""

from __future__ import annotations

TECH_FINGERPRINTS = [

    {
        "name": "Next.js",
        "category": "javascript",

        "headers": [],

        "meta": [],

        "scripts": [
            "_next/",
            "__next",
            "next/static",
        ],

        "inline": [
            "__NEXT_DATA__",
            "__next",
        ],

        "dom": [],

        "cookies": [],

        "version": [],

        "confidence": 0.99,
    },

    {
        "name": "React",

        "category": "javascript",

        "headers": [],

        "meta": [],

        "scripts": [
            "react",
            "react-dom",
        ],

        "inline": [
            "__REACT_DEVTOOLS_GLOBAL_HOOK__",
        ],

        "dom": [
            "data-reactroot",
        ],

        "cookies": [],

        "version": [],

        "confidence": 0.98,
    },

    {
        "name": "Vue.js",

        "category": "javascript",

        "headers": [],

        "meta": [],

        "scripts": [
            "vue.runtime",
            "vue.global",
            "vue.esm",
        ],

        "inline": [
            "__VUE__",
            "__VUE_DEVTOOLS_GLOBAL_HOOK__",
        ],

        "dom": [
            "data-v-",
            "v-cloak",
        ],

        "cookies": [],

        "version": [],

        "confidence": 0.98,
    },

    {
        "name": "WordPress",

        "category": "cms",

        "headers": [],

        "meta": [
            "wordpress",
        ],

        "scripts": [
            "wp-content",
            "wp-includes",
        ],

        "inline": [],

        "dom": [],

        "cookies": [
            "wordpress_logged_in",
            "wp-settings",
        ],

        "version": [],

        "confidence": 0.99,
    },

    {
        "name": "Shopify",

        "category": "cms",

        "headers": [
            "x-shopify",
        ],

        "meta": [],

        "scripts": [
            "cdn.shopify.com",
        ],

        "inline": [],

        "dom": [],

        "cookies": [
            "_shopify_y",
            "_shopify_s",
        ],

        "version": [],

        "confidence": 0.99,
    },

]