"""Script to export OpenAPI schema and generate the route inventory."""

import os
import json
import sys
from fastapi.openapi.utils import get_openapi
from app.main import app

def generate_and_export():
    # Ensure reports directory exists
    os.makedirs("reports", exist_ok=True)
    
    # 1. Export OpenAPI JSON
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    
    openapi_path = os.path.join("reports", "openapi.json")
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"OpenAPI schema successfully exported to: {openapi_path}")

    # 2. Generate Route Inventory Markdown
    routes_md = []
    routes_md.append("# NeuroSentio Copilot Agent — API Route Inventory")
    routes_md.append("")
    routes_md.append("This document list all registered API endpoints, their HTTP methods, handler functions, and brief summary descriptions.")
    routes_md.append("")
    routes_md.append("> [!NOTE]")
    routes_md.append("> **Transition Route Resolution**: In some early design specifications, a route named `/tasks/{id}/transition` was mentioned. This route has been consolidated into the unified transition script route group `/transitions/generate`. Use `POST /transitions/generate` for all transition script generation.")
    routes_md.append("")
    routes_md.append("| Method | Path | Summary / Function | Tag |")
    routes_md.append("|---|---|---|---|")

    # Gather routes
    from fastapi.routing import APIRoute
    api_routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            api_routes.append(route)
            
    # Sort routes by path
    api_routes.sort(key=lambda r: r.path)

    for route in api_routes:
        methods_str = ", ".join(route.methods)
        summary = route.summary or route.description or "No description"
        # Truncate summary if too long
        if len(summary) > 80:
            summary = summary[:77] + "..."
        # Clean up any newlines in summary for markdown table
        summary = summary.replace("\n", " ").replace("\r", "")
        
        tag = route.tags[0] if route.tags else "General"
        routes_md.append(f"| `{methods_str}` | `{route.path}` | {summary} | {tag} |")

    routes_md.append("")
    routes_md.append(f"**Total Registered App Routes**: {len(api_routes)}")
    routes_md.append("")
    
    inventory_path = os.path.join("reports", "routes_inventory.md")
    with open(inventory_path, "w", encoding="utf-8") as f:
        f.write("\n".join(routes_md))
    print(f"Routes inventory successfully generated at: {inventory_path}")


if __name__ == "__main__":
    generate_and_export()
