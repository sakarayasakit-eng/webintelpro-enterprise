"""
WebIntelPro Enterprise X
CMS Fingerprints
"""

FINGERPRINTS = [

    {
        "name": "WordPress",
        "category": "cms",

        "headers": [],

        "meta": [
            "wordpress",
            "wp-generator",
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
            "shopifycdn",
        ],

        # Modern (incl. headless) storefronts serve product imagery from
        # cdn.shopify.com via <img>/srcset and reference *.myshopify.com, so
        # the tell-tale hosts live in the raw HTML, not in <script src>.
        "html": [
            "cdn.shopify.com",
            "myshopify",
        ],

        "inline": [],

        "dom": [],

        "cookies": [
            "_shopify_y",
            "_shopify_s",
        ],
    },

    {
        "name": "Drupal",
        "category": "cms",

        # Drupal 8-10 emit "X-Generator: Drupal 10 (https://www.drupal.org)".
        "headers": [
            "x-generator:drupal",
        ],

        "meta": [
            "drupal",
        ],

        "scripts": [
            "/sites/default/",
            "/core/misc/drupal.js",
        ],

        # Modern Drupal ships settings as <script data-drupal-selector> /
        # drupalSettings, and marks the DOM with data-drupal-* attributes.
        "inline": [
            "drupal-settings-json",
            "drupalsettings",
        ],

        "dom": [
            "data-drupal-",
        ],

        "cookies": [],
    },

    {
        "name": "Joomla",

        "category": "cms",

        "headers": [],

        "meta": [
            "joomla",
        ],

        "scripts": [
            "/media/system/",
        ],

        "inline": [],

        "dom": [],

        "cookies": [],
    },

]