import sys
from app.main import app

def list_routes():
    routes = []
    for route in app.routes:
        # Check if it has a methods attribute (APIRoute)
        methods = getattr(route, "methods", None)
        if methods:
            methods_str = ",".join(methods)
            routes.append(f"{methods_str} {route.path} {route.name}")
        else:
            routes.append(f"GET {route.path} {route.name}")
    print(f"Total Routes: {len(app.routes)}")
    for r in sorted(routes):
        print(r)

if __name__ == "__main__":
    list_routes()
