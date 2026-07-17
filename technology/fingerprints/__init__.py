"""
WebIntelPro Enterprise X
Enterprise Fingerprint Loader

Aggregates every per-category fingerprint module into a single
TECH_FINGERPRINTS list consumed by the detector.
"""

from .javascript import FINGERPRINTS as JAVASCRIPT
from .js_libraries import FINGERPRINTS as JS_LIBRARIES
from .build_tools import FINGERPRINTS as BUILD_TOOLS
from .cms import FINGERPRINTS as CMS
from .cms_extra import FINGERPRINTS as CMS_EXTRA
from .servers import FINGERPRINTS as SERVERS
from .server_extra import FINGERPRINTS as SERVER_EXTRA
from .css import FINGERPRINTS as CSS
from .analytics import FINGERPRINTS as ANALYTICS
from .analytics_extra import FINGERPRINTS as ANALYTICS_EXTRA
from .cdn import FINGERPRINTS as CDN
from .cdn_extra import FINGERPRINTS as CDN_EXTRA
from .cookies import FINGERPRINTS as COOKIES
from .frameworks import FINGERPRINTS as FRAMEWORKS
from .hosting import FINGERPRINTS as HOSTING
from .hosting_extra import FINGERPRINTS as HOSTING_EXTRA
from .security import FINGERPRINTS as SECURITY
from .ecommerce import FINGERPRINTS as ECOMMERCE
from .payments import FINGERPRINTS as PAYMENTS
from .marketing import FINGERPRINTS as MARKETING
from .chat import FINGERPRINTS as CHAT
from .fonts import FINGERPRINTS as FONTS
from .misc import FINGERPRINTS as MISC

from .fp_extra_js import FINGERPRINTS as X_JS
from .fp_extra_analytics import FINGERPRINTS as X_ANALYTICS
from .fp_extra_marketing import FINGERPRINTS as X_MARKETING
from .fp_extra_cms import FINGERPRINTS as X_CMS
from .fp_extra_frameworks import FINGERPRINTS as X_FRAMEWORKS
from .fp_extra_infra import FINGERPRINTS as X_INFRA
from .fp_extra_ecommerce import FINGERPRINTS as X_ECOMMERCE
from .fp_widgets import FINGERPRINTS as X_WIDGETS
from .fp_more import FINGERPRINTS as X_MORE


TECH_FINGERPRINTS = (
    JAVASCRIPT + JS_LIBRARIES + BUILD_TOOLS
    + CMS + CMS_EXTRA
    + SERVERS + SERVER_EXTRA
    + CSS
    + ANALYTICS + ANALYTICS_EXTRA
    + CDN + CDN_EXTRA
    + COOKIES
    + FRAMEWORKS
    + HOSTING + HOSTING_EXTRA
    + SECURITY + ECOMMERCE + PAYMENTS + MARKETING + CHAT + FONTS + MISC
    + X_JS + X_ANALYTICS + X_MARKETING + X_CMS + X_FRAMEWORKS
    + X_INFRA + X_ECOMMERCE + X_WIDGETS + X_MORE
)
