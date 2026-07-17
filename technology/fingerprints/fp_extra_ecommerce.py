"""WebIntelPro Enterprise X - Extra e-commerce / subscriptions / checkout."""
def e(name, headers=(), scripts=(), inline=(), dom=(), cookies=()):
    return {"name": name, "category": "ecommerce", "headers": list(headers), "meta": [],
            "scripts": list(scripts), "inline": list(inline), "dom": list(dom), "cookies": list(cookies)}
FINGERPRINTS = [
    e("Shopify Plus", headers=["x-shopify-stage"], scripts=["shopifycloud"], inline=["shopify.shop"]),
    e("Commerce Layer", scripts=["commercelayer"], inline=["commercelayer"]),
    e("Swell", scripts=["swell.js", "swell.store"], inline=["swell.init"]),
    e("Foxy.io", scripts=["cdn.foxycart.com"], inline=["foxycart"]),
    e("Recharge", scripts=["static.rechargecdn.com"], inline=["recharge"]),
    e("Bold Commerce", scripts=["cdn.boldapps.net"], inline=["boldcommerce"]),
    e("Gumroad", scripts=["gumroad.com/js"], inline=["gumroad"], dom=["gumroad-"]),
    e("Lemon Squeezy", scripts=["lemonsqueezy.com", "lmsqueezy"], inline=["lemonsqueezy"]),
    e("Paddle", scripts=["cdn.paddle.com", "paddle.js"], inline=["paddle.setup"]),
    e("FastSpring", scripts=["sbl.onfastspring.com"], inline=["fastspring"]),
    e("Chargebee", scripts=["js.chargebee.com"], inline=["chargebee.init"]),
    e("Sezzle", scripts=["widget.sezzle.com"], inline=["sezzle"], dom=["sezzle-"]),
    e("Affirm", scripts=["cdn1.affirm.com"], inline=["affirm.ui"], dom=["affirm-"]),
]
