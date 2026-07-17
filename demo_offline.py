"""Offline demo: runs the full pipeline on a realistic fixture and writes
console/JSON/HTML/Excel/PDF sample reports. (Sandbox networking is blocked;
on a real machine use `python main.py <url> -f all`.)"""

from engine import AnalysisEngine
from reporter import ReportGenerator

HTML = """<html lang="en"><head>
<title>Nimbus Store - Premium Outdoor Gear and Camping Equipment</title>
<meta name="generator" content="WordPress 6.4.2">
<meta name="description" content="Nimbus Store offers premium outdoor gear,
camping equipment and hiking essentials with free shipping over fifty dollars.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://nimbus.example/">
<meta property="og:title" content="Nimbus Store">
<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter">
<link rel="stylesheet" href="https://use.fontawesome.com/releases/v6.5.1/css/all.css">
<script src="/wp-content/plugins/woocommerce/assets/js/frontend/cart.js"></script>
<script src="https://js.stripe.com/v3/"></script>
<script src="https://widget.intercom.io/widget/xyz"></script>
<script src="https://www.googletagmanager.com/gtag/js?id=G-ABC123"></script>
<script src="https://connect.facebook.net/en_US/fbevents.js"></script>
<script src="https://cdn.jsdelivr.net/npm/alpinejs@3.13.0/dist/cdn.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product"}</script>
</head><body class="woocommerce home" x-data="{open:false}">
<h1>Premium Outdoor Gear</h1><h2>Featured</h2>
<div class="g-recaptcha"></div><i class="fa-solid fa-cart"></i>
<img src="tent.jpg" alt="Two person tent"><img src="stove.jpg"><img src="pack.jpg" alt="Hiking backpack">
<script>Stripe('pk_live'); Intercom('boot'); fbq('init','111'); new Chart();</script>
</body></html>"""

HEADERS = {"Server": "nginx/1.25.3", "X-Powered-By": "PHP/8.2.15",
           "Content-Encoding": "gzip", "Cache-Control": "public, max-age=3600",
           "CF-RAY": "8abc-LHR", "Strict-Transport-Security": "max-age=31536000",
           "X-Content-Type-Options": "nosniff"}
COOKIES = {"woocommerce_cart_hash": "9f", "__cf_bm": "aa", "_ga": "GA1.2"}

result = AnalysisEngine().analyze("https://nimbus.example/", HTML, HEADERS, COOKIES)
rep = ReportGenerator()
print(rep.console_str(result))
rep.save_json(result, "reports/sample_report.json")
rep.save_html(result, "reports/sample_report.html")
rep.save_excel(result, "reports/sample_report.xlsx")
rep.save_pdf(result, "reports/sample_report.pdf")
print("\n[saved] reports/sample_report.{json,html,xlsx,pdf}")
