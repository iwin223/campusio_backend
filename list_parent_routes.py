from server import app

# Get all routes
routes = []
for route in app.routes:
    if hasattr(route, 'path') and 'parent' in route.path:
        routes.append({
            'path': route.path,
            'methods': list(route.methods) if hasattr(route, 'methods') else []
        })

routes.sort(key=lambda x: x['path'])
print('Parent Portal Routes:')
print('='*70)
for route in routes:
    print(f"{route['path']:<60} {route['methods']}")
