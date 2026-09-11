"""Production entrypoint for DataKite AI.
Kept separate from app.py so hosting platforms can use a stable module.
"""
from app import app

application = app
