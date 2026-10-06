"""Vercel entry point: exposes the Flask app as a serverless function."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401


class VercelPathMiddleware:
    """Restores the original request URL when Vercel rewrites requests to /api/index."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        # Vercel rewrites to /api/index or /api/index.py
        if path in ("/api/index", "/api/index.py", "/api"):
            orig = (
                environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
                or environ.get("HTTP_X_ORIGINAL_URI")
                or environ.get("HTTP_X_FORWARDED_URI")
                or environ.get("RAW_URI")
                or environ.get("REQUEST_URI")
            )
            # Check if passed via query string __path
            if not orig and "__path=" in environ.get("QUERY_STRING", ""):
                import urllib.parse
                qs = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
                if "__path" in qs:
                    orig = "/" + qs["__path"][0].lstrip("/")
            if orig:
                orig_path = orig.split("?")[0]
                if orig_path:
                    environ["PATH_INFO"] = orig_path
        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
