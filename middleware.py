import time
import logging
import uuid
import json
import base64
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from config import get_settings

settings = get_settings()
logger = logging.getLogger("uvicorn.access")
logger.disabled = True

request_logger = logging.getLogger("request_logger")
request_logger.setLevel(logging.INFO)

# Context variables for request tracking
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60

rate_limit_storage = defaultdict(list)






def register_middleware(app: FastAPI):

    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
    
  
