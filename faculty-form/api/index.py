"""Vercel entry point: exposes the Flask app as a serverless function."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401


class VercelPathMiddleware:
    """Restores the original request URL from Vercel's rewrite query parameter."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs_str = environ.get("QUERY_STRING", "")
        if "path=" in qs_str:
            import urllib.parse
            qs = urllib.parse.parse_qs(qs_str)
            if "path" in qs:
                val = qs["path"][0].strip()
                environ["PATH_INFO"] = "/" + val.lstrip("/") if val else "/"
                # Clean up 'path' parameter from query string so request.args is untouched
                new_qs = {k: v for k, v in qs.items() if k != "path"}
                environ["QUERY_STRING"] = urllib.parse.urlencode(new_qs, doseq=True)
        elif environ.get("PATH_INFO") in ("/api/index", "/api/index/"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
