"""
E-Mall SASRec API — Configuration
==================================
Centralised config for paths, hyperparameters, and CORS origins.
"""

import os

# ── Paths ───────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR  # GP - Dataset folder
API_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_CHECKPOINT_PATH = os.path.join(API_DIR, "checkpoints", "sasrec_emall.pth")
PRODUCT_MAPPINGS_PATH = os.path.join(DATA_DIR, "product_mappings.csv")
PRODUCTS_CSV_PATH = os.path.join(DATA_DIR, "products.csv")
INTERACTIONS_CSV_PATH = os.path.join(DATA_DIR, "interactions.csv")

# ── Model Hyperparameters (must match training) ─────────────────
MAX_SEQ_LEN = 50
HIDDEN_DIM = 64
NUM_BLOCKS = 2
NUM_HEADS = 1
DROPOUT_RATE = 0.2

# ── API Settings ────────────────────────────────────────────────
API_TITLE = "E-Mall SASRec Recommendation API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
AI-powered product recommendation engine for the E-Mall platform.
Uses a Self-Attentive Sequential Recommendation (SASRec) model
to predict the next products a user is likely to interact with,
based on their chronological interaction history.
"""

DEFAULT_TOP_K = 10
MAX_TOP_K = 50

# ── CORS ────────────────────────────────────────────────────────
CORS_ORIGINS = [
    "http://localhost:3000",      # React dev
    "http://localhost:5173",      # Vite dev
    "http://localhost:5000",      # .NET backend
    "https://localhost:5001",     # .NET HTTPS
    "http://localhost:7000",
    "https://localhost:7001",
    "*",                          # Allow all during development
]
