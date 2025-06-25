"""
Main FastAPI application module that serves as the entry point
or the web server. Defines the core API routes
and application configuration.
"""
from fastapi import FastAPI

app = FastAPI()


@app.get(
    '/',
    summary='Root route',
    description='Returns a simple Hello World message'
)
def read_root():
    return {'Hello': 'World'}


@app.get(
    '/health',
    summary='Health check',
    description='Returns the health status of the API'
)
def read_health():
    return {'status': 'ok'}
