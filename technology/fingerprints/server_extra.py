"""WebIntelPro Enterprise X - Additional Web Server / App Server Fingerprints"""

def _fp(name, headers=(), inline=(), scripts=()):
    return {"name": name, "category": "server", "headers": list(headers),
            "meta": [], "scripts": list(scripts), "inline": list(inline),
            "dom": [], "cookies": []}

FINGERPRINTS = [
    _fp("OpenResty", headers=["openresty"]),
    _fp("Apache Tomcat", headers=["tomcat", "coyote"]),
    _fp("Jetty", headers=["jetty"]),
    _fp("Gunicorn", headers=["gunicorn"]),
    _fp("uWSGI", headers=["uwsgi"]),
    _fp("Kestrel", headers=["kestrel"]),
    _fp("Cowboy", headers=["cowboy"]),
    _fp("Traefik", headers=["traefik"]),
    _fp("Envoy", headers=["envoy", "x-envoy"]),
    _fp("HAProxy", headers=["haproxy"]),
    _fp("Varnish", headers=["varnish", "x-varnish", "via:varnish"]),
    _fp("Google Frontend", headers=["gfe", "server:gws", "server:gse"]),
    _fp("Phusion Passenger", headers=["passenger"]),
    _fp("Werkzeug", headers=["werkzeug"]),
    _fp("Google Servlet Engine", headers=["gse"]),
]
