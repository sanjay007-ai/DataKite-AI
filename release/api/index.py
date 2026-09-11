import os, sys
ROOT=os.path.dirname(os.path.dirname(__file__))
BACKEND=os.path.join(ROOT,"backend")
if BACKEND not in sys.path: sys.path.insert(0, BACKEND)
os.environ.setdefault("VERCEL","1")
from app import app
