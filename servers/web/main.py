"""
Main FastAPI application module that serves as the entry point for the web server.
Defines the core API routes and application configuration.
"""
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
def read_health():
    return {"status": "ok"}

