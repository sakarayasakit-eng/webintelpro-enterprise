"""
WebIntelPro Enterprise X
JavaScript Framework Fingerprints
"""

FINGERPRINTS = [

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
        # Next.js is a React meta-framework; its production bundle hashes the
        # React runtime so no direct "react" marker survives. Entail it.
        "implies": ["React"],
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
            "__VUE_DEVTOOLS_GLOBAL_HOOK__",
        ],
        "dom": [
            "v-cloak",
            "data-v-",
        ],
        "cookies": [],
    },

]