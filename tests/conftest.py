"""Shared fixtures for WebIntelPro tests."""

import os
import sys

import pytest

# Ensure the project root is importable when running pytest from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def wordpress_html():
    return """<html lang="en"><head>
    <title>Acme Store - Best Widgets Online Shop Today</title>
    <meta name="generator" content="WordPress 6.4">
    <meta name="description" content="Acme Store sells the finest widgets on the
    internet with fast shipping, great prices and a thirty day money back guarantee.">
    <link rel="canonical" href="https://acme.example/">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto">
    <script src="/wp-content/plugins/woocommerce/assets/js/frontend.js"></script>
    <script src="https://js.stripe.com/v3/"></script>
    <script src="https://widget.intercom.io/widget/abc"></script>
    <script type="application/ld+json">{"@type":"Product"}</script>
    </head><body class="woocommerce home">
    <h1>Welcome to Acme</h1>
    <img src="a.png" alt="A widget"><img src="b.png">
    <script>Stripe('pk'); Intercom('boot');</script>
    </body></html>"""


@pytest.fixture
def wordpress_headers():
    return {
        "Server": "nginx/1.25.3",
        "X-Powered-By": "PHP/8.2",
        "Strict-Transport-Security": "max-age=63072000",
        "Content-Encoding": "gzip",
        "Cache-Control": "max-age=3600",
    }


@pytest.fixture
def wordpress_cookies():
    return {"woocommerce_cart_hash": "abc", "wordpress_logged_in": "x"}
