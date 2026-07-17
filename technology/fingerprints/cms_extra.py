"""
WebIntelPro Enterprise X
Enterprise CMS Fingerprints
"""


def _fp(
    name,
    headers=(),
    meta=(),
    scripts=(),
    inline=(),
    dom=(),
    cookies=(),
    html=(),
):
    fp = {
        "name": name,
        "category": "cms",
        "headers": list(headers),
        "meta": list(meta),
        "scripts": list(scripts),
        "inline": list(inline),
        "dom": list(dom),
        "cookies": list(cookies),
    }
    if html:
        # Raw-document source: for signals (asset-CDN hosts, CSP tokens) that
        # only appear outside parsed nodes. See technology/matcher.py.
        fp["html"] = list(html)
    return fp


FINGERPRINTS = [

    # ------------------------------------------------------------------
    # Ghost
    # ------------------------------------------------------------------

    _fp(
        "Ghost",
        meta=[
            # meta_text() exposes only meta names + values (never raw
            # attribute markup), so the old 'content="ghost' patterns could
            # never fire. The <meta name="generator"> value is "Ghost x.y".
            "ghost",
        ],
        scripts=[
            "/ghost/",
            "ghost.min.js",
            "/members/",
        ],
        inline=[
            "ghost.init",
        ],
        cookies=[
            "__ghost",
        ],
    ),

    # ------------------------------------------------------------------
    # Contentful
    # ------------------------------------------------------------------

    _fp(
        "Contentful",
        headers=[
            "x-contentful",
            "cdn.contentful.com",
        ],
        scripts=[
            "ctfassets.net",
            "cdn.contentful.com",
        ],
        inline=[
            "window.contentful",
            "contentful.createclient",
        ],
        # ctfassets.net is Contentful's asset host; it appears in <img>/srcset
        # on Contentful-backed sites and is unique to the platform.
        html=[
            "ctfassets.net",
        ],
    ),

    # ------------------------------------------------------------------
    # Sanity
    # ------------------------------------------------------------------

    _fp(
        "Sanity",
        scripts=[
            "cdn.sanity.io",
        ],
        inline=[
            "__sanity",
            "__sanity_client",
        ],
        # cdn.sanity.io / apicdn.sanity.io serve Sanity-managed assets via
        # <img>/srcset; unique to the platform.
        html=[
            "cdn.sanity.io",
            "apicdn.sanity.io",
        ],
    ),

    # ------------------------------------------------------------------
    # Strapi
    # ------------------------------------------------------------------

    _fp(
        "Strapi",
        headers=[
            "strapi",
        ],
        cookies=[
            "strapi",
        ],
    ),

    # ------------------------------------------------------------------
    # Webflow
    # ------------------------------------------------------------------

    _fp(
        "Webflow",
        meta=[
            'generator" content="webflow',
        ],
        scripts=[
            "webflow.js",
        ],
        dom=[
            "w-nav",
            "w-slider",
            "w-form",
        ],
    ),

    # ------------------------------------------------------------------
    # Framer
    # ------------------------------------------------------------------

    _fp(
        "Framer",
        meta=[
            "framer",
        ],
        scripts=[
            "framerusercontent.com",
        ],
        dom=[
            "framer-",
        ],
    ),

    # ------------------------------------------------------------------
    # Wix
    # ------------------------------------------------------------------

    _fp(
        "Wix",
        headers=[
            "x-wix-request-id",
        ],
        scripts=[
            "static.parastorage.com",
        ],
        cookies=[
            "svsession",
        ],
    ),

    # ------------------------------------------------------------------
    # Squarespace
    # ------------------------------------------------------------------

    _fp(
        "Squarespace",
        scripts=[
            "static1.squarespace.com",
        ],
        dom=[
            "sqs-",
        ],
    ),

    # ------------------------------------------------------------------
    # Blogger
    # ------------------------------------------------------------------

    _fp(
        "Blogger",
        meta=[
            "blogger",
        ],
        scripts=[
            "blogger.com",
        ],
    ),

    # ------------------------------------------------------------------
    # Adobe Experience Manager
    # ------------------------------------------------------------------

    _fp(
        "Adobe Experience Manager",
        scripts=[
            "/etc.clientlibs/",
            "/libs/granite/",
        ],
        dom=[
            "cq-editable",
        ],
    ),

    # ------------------------------------------------------------------
    # HubSpot CMS
    # ------------------------------------------------------------------

    _fp(
        "HubSpot CMS",
        scripts=[
            "hubspotusercontent",
        ],
        inline=[
            "_hsq",
        ],
    ),

    # ------------------------------------------------------------------
    # TYPO3
    # ------------------------------------------------------------------

    _fp(
        "TYPO3",
        scripts=[
            "/typo3conf/",
        ],
        cookies=[
            "fe_typo_user",
        ],
    ),

    # ------------------------------------------------------------------
    # Sitecore
    # ------------------------------------------------------------------

    _fp(
        "Sitecore",
        scripts=[
            "/sitecore/",
        ],
        cookies=[
            "sc_analytics",
        ],
    ),

    # ------------------------------------------------------------------
    # Bitrix
    # ------------------------------------------------------------------

    _fp(
        "Bitrix",
        scripts=[
            "/bitrix/",
        ],
        cookies=[
            "bitrix_",
        ],
    ),

    # ------------------------------------------------------------------
    # Umbraco
    # ------------------------------------------------------------------

    _fp(
        "Umbraco",
        cookies=[
            "umb_",
        ],
    ),
]