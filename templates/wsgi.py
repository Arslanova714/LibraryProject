import sys
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
import uvicorn
from main import app as fastapi_app

# Это стандартный WSGI-адаптер для FastAPI
from asgi.wsgi import WsgiToAsgi

application = WsgiToAsgi(fastapi_app)