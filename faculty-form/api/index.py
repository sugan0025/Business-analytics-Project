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
        orig = None
        # 1. Check query string __path from vercel.json rewrite
        qs_str = environ.get("QUERY_STRING", "")
        if "__path=" in qs_str:
            import urllib.parse
            qs = urllib.parse.parse_qs(qs_str)
            if "__path" in qs:
                val = qs["__path"][0].strip()
                orig = "/" + val.lstrip("/") if val else "/"
                # Clean up __path from query string
                new_qs = {k: v for k, v in qs.items() if k != "__path"}
                environ["QUERY_STRING"] = urllib.parse.urlencode(new_qs, doseq=True)

        # 2. Check Vercel headers if __path wasn't present
        if not orig:
            orig = (
                environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
                or environ.get("HTTP_X_ORIGINAL_URI")
                or environ.get("HTTP_X_FORWARDED_URI")
            )

        if orig:
            orig_path = orig.split("?")[0]
            if orig_path:
                environ["PATH_INFO"] = orig_path
        elif environ.get("PATH_INFO") in ("/api/index", "/api/index.py", "/api"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
