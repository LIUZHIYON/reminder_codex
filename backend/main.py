import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)

from database import init_db
from routes.reminders import router as reminders_router
from services.scheduler import start_scheduler, stop_scheduler
import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    await init_db()
    print(f"[App] Database initialized")
    await start_scheduler()
    print(f"[App] Server starting at http://{config.HOST}:{config.PORT}")
    yield
    await stop_scheduler()
    print("[App] Server stopped")

app = FastAPI(title="DingDing Reminder", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(reminders_router)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] Unhandled exception: {exc}")
    print(f"  Path: {request.url.path}")
    print(f"  Method: {request.method}")
    import traceback
    traceback.print_exc()
    return Response(status_code=500, content="Internal Server Error")

# Serve frontend
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_dir, "frontend")

if os.path.exists(frontend_dir):
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
    print(f"[App] Frontend served from: {frontend_dir}")
else:
    print(f"[App] Warning: Frontend not found at {frontend_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
