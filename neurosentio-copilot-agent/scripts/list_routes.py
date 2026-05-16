"""Utility script to list all API routes."""
from app.main import app

SKIP = {'/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect'}
business = []
for r in app.routes:
    if hasattr(r, 'methods') and r.path not in SKIP:
        methods = r.methods - {'HEAD', 'OPTIONS'}
        if methods:
            business.append((sorted(methods), r.path))

business.sort(key=lambda x: x[1])
print(f"Business endpoints: {len(business)}")
for m, p in business:
    print(f"  {','.join(m):6s}  {p}")
