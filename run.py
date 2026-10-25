"""Start Poacher Guard:  python run.py   (then open http://localhost:8000)"""
import os
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")   # hide OpenCV probe warnings
import logging

import uvicorn

from app.config import load_config
from app.server import create_app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = load_config()
    uvicorn.run(create_app(cfg), host=cfg["server"].get("host", "0.0.0.0"),
                port=cfg["server"].get("port", 8000), log_level="warning")
