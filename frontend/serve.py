"""Simple static file server for the frontend production build."""
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

app = Starlette()

# Serve static assets
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

# Serve favicon
@app.route("/favicon.svg")
async def favicon(request):
    return FileResponse("dist/favicon.svg")

# SPA fallback: return index.html for all other routes
@app.route("/{path:path}")
async def spa(request):
    return FileResponse("dist/index.html")

@app.route("/")
async def root(request):
    return FileResponse("dist/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5273)
