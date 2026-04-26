"""
E-Mall SASRec — FastAPI Recommendation Service
================================================
Production-ready REST API that serves real-time product recommendations
using a pre-trained SASRec (Self-Attentive Sequential Recommendation) model.

Endpoints:
    GET  /health             - Health check & model status
    POST /recommend          - Top-K recommendations for a single user
    POST /recommend/batch    - Batch recommendations for multiple users
    POST /recommend/sequence - Recommendations from a raw item sequence
    POST /recommend/similar  - Find similar items via embedding cosine similarity

Usage:
    cd "GP - Dataset"
    uvicorn api.main:app --reload --port 8000

API Docs:
    http://localhost:8000/docs  (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add api/ to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    API_TITLE, API_VERSION, API_DESCRIPTION,
    CORS_ORIGINS, MODEL_CHECKPOINT_PATH,
    MAX_SEQ_LEN, HIDDEN_DIM, NUM_BLOCKS, NUM_HEADS, DROPOUT_RATE,
)
from model import SASRec
from schemas import (
    RecommendRequest, RecommendResponse, RecommendedProduct,
    BatchRecommendRequest, BatchRecommendResponse,
    SimilarItemsRequest, SimilarItemsResponse,
    SequenceRecommendRequest,
    HealthResponse, ErrorResponse,
)

# ── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)
logger = logging.getLogger("sasrec-api")


# ═══════════════════════════════════════════════════════════════
#  Global state (loaded once at startup)
# ═══════════════════════════════════════════════════════════════

class ModelState:
    """Container for the loaded model and associated data."""

    def __init__(self):
        self.model: SASRec | None = None
        self.device: torch.device = torch.device("cpu")
        self.item2idx: dict = {}
        self.idx2item: dict = {}
        self.user_sequences: dict = {}
        self.product_meta: dict = {}
        self.num_items: int = 0
        self.num_users: int = 0
        self.is_loaded: bool = False

    def load(self):
        """Load the trained model checkpoint into memory."""
        if not os.path.exists(MODEL_CHECKPOINT_PATH):
            logger.error(
                f"Checkpoint not found at {MODEL_CHECKPOINT_PATH}. "
                f"Run 'python api/train_and_save.py' first."
            )
            return

        logger.info(f"Loading checkpoint from {MODEL_CHECKPOINT_PATH}...")
        t0 = time.time()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        checkpoint = torch.load(MODEL_CHECKPOINT_PATH, map_location=self.device, weights_only=False)

        hp = checkpoint["hyperparams"]
        self.num_items = hp["num_items"]

        self.model = SASRec(
            num_items=hp["num_items"],
            max_len=hp["max_len"],
            hidden_dim=hp["hidden_dim"],
            num_blocks=hp["num_blocks"],
            num_heads=hp["num_heads"],
            dropout_rate=hp["dropout_rate"],
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

        self.item2idx = checkpoint["item2idx"]
        self.idx2item = checkpoint["idx2item"]
        self.user_sequences = checkpoint["user_sequences"]
        self.product_meta = checkpoint.get("product_meta", {})
        self.num_users = len(self.user_sequences)
        self.is_loaded = True

        elapsed = time.time() - t0
        logger.info(
            f"[OK] Model loaded in {elapsed:.2f}s - "
            f"{self.num_items - 1} items, {self.num_users:,} users, device={self.device}"
        )
        if "metrics" in checkpoint:
            m = checkpoint["metrics"]
            logger.info(
                f"   Model metrics - Test HR@10: {m.get('test_hr_at_10', 'N/A')}, "
                f"Test NDCG@10: {m.get('test_ndcg_at_10', 'N/A')}"
            )


state = ModelState()


# ═══════════════════════════════════════════════════════════════
#  Lifespan: load model on startup
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    state.load()
    yield
    logger.info("Shutting down SASRec API...")


# ═══════════════════════════════════════════════════════════════
#  FastAPI App
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  Helper Functions
# ═══════════════════════════════════════════════════════════════

def _ensure_model():
    """Raise 503 if the model isn't loaded yet."""
    if not state.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run 'python api/train_and_save.py' first, then restart the server.",
        )


def _enrich_product(rank: int, product_id: int, score: float) -> RecommendedProduct:
    """Add product metadata to a recommendation."""
    meta = state.product_meta.get(product_id, {})
    return RecommendedProduct(
        rank=rank,
        product_id=product_id,
        score=round(float(score), 4),
        product_name=meta.get("product_name"),
        category=meta.get("category"),
        price=meta.get("price"),
        image_url=meta.get("image_url"),
    )


def _recommend_for_user(
    user_id: int,
    top_k: int = 10,
    exclude_interacted: bool = True,
) -> list[RecommendedProduct]:
    """Core recommendation logic for a single user."""
    if user_id not in state.user_sequences:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} has no interaction history.",
        )

    seq = state.user_sequences[user_id][-MAX_SEQ_LEN:]
    padded = [0] * (MAX_SEQ_LEN - len(seq)) + seq

    # Score all items
    all_items = list(range(1, state.num_items))
    seq_t = torch.LongTensor([padded]).to(state.device)
    item_t = torch.LongTensor([all_items]).to(state.device)

    with torch.no_grad():
        scores = state.model.predict(seq_t, item_t)[0].cpu().numpy()

    # Optionally filter out interacted items
    history_set = set(state.user_sequences[user_id]) if exclude_interacted else set()

    # Sort by score descending
    item_scores = sorted(zip(all_items, scores), key=lambda x: x[1], reverse=True)

    results = []
    for item_idx, score in item_scores:
        if item_idx in history_set:
            continue
        product_id = state.idx2item.get(item_idx, item_idx)
        results.append(_enrich_product(len(results) + 1, product_id, score))
        if len(results) >= top_k:
            break

    return results


def _recommend_from_sequence(
    product_ids: list[int],
    top_k: int = 10,
    exclude_input: bool = True,
) -> list[RecommendedProduct]:
    """Generate recommendations from a raw product ID sequence (no user needed)."""
    # Map product IDs to internal indices
    seq = [state.item2idx[pid] for pid in product_ids if pid in state.item2idx]
    if not seq:
        raise HTTPException(
            status_code=400,
            detail="None of the provided product_ids are known to the model.",
        )

    seq = seq[-MAX_SEQ_LEN:]
    padded = [0] * (MAX_SEQ_LEN - len(seq)) + seq

    all_items = list(range(1, state.num_items))
    seq_t = torch.LongTensor([padded]).to(state.device)
    item_t = torch.LongTensor([all_items]).to(state.device)

    with torch.no_grad():
        scores = state.model.predict(seq_t, item_t)[0].cpu().numpy()

    exclude_set = set(seq) if exclude_input else set()
    item_scores = sorted(zip(all_items, scores), key=lambda x: x[1], reverse=True)

    results = []
    for item_idx, score in item_scores:
        if item_idx in exclude_set:
            continue
        product_id = state.idx2item.get(item_idx, item_idx)
        results.append(_enrich_product(len(results) + 1, product_id, score))
        if len(results) >= top_k:
            break

    return results


# ═══════════════════════════════════════════════════════════════
#  Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check & model status",
)
async def health():
    """Returns the current status of the API and model."""
    return HealthResponse(
        status="ok" if state.is_loaded else "model_not_loaded",
        model_loaded=state.is_loaded,
        num_items=state.num_items - 1 if state.is_loaded else 0,
        num_users=state.num_users,
        device=str(state.device),
        model_version=API_VERSION,
    )


@app.post(
    "/recommend",
    response_model=RecommendResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Recommendations"],
    summary="Get top-K recommendations for a user",
)
async def recommend(request: RecommendRequest):
    """
    Generate personalised product recommendations for a specific user
    based on their chronological interaction history.

    The model uses the user's most recent interactions (up to 50 items)
    to predict which products they are most likely to engage with next.
    """
    _ensure_model()
    recommendations = _recommend_for_user(
        user_id=request.user_id,
        top_k=request.top_k,
        exclude_interacted=request.exclude_interacted,
    )
    return RecommendResponse(
        user_id=request.user_id,
        recommendations=recommendations,
        model_version=API_VERSION,
    )


@app.post(
    "/recommend/batch",
    response_model=BatchRecommendResponse,
    responses={503: {"model": ErrorResponse}},
    tags=["Recommendations"],
    summary="Batch recommendations for multiple users",
)
async def recommend_batch(request: BatchRecommendRequest):
    """
    Generate recommendations for multiple users in a single request.
    Users without interaction history will be skipped with empty recommendations.
    """
    _ensure_model()
    results = []
    for uid in request.user_ids:
        try:
            recs = _recommend_for_user(
                user_id=uid,
                top_k=request.top_k,
                exclude_interacted=request.exclude_interacted,
            )
        except HTTPException:
            recs = []

        results.append(RecommendResponse(
            user_id=uid,
            recommendations=recs,
            model_version=API_VERSION,
        ))

    return BatchRecommendResponse(results=results, model_version=API_VERSION)


@app.post(
    "/recommend/sequence",
    response_model=RecommendResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Recommendations"],
    summary="Get recommendations from a product sequence",
)
async def recommend_from_sequence(request: SequenceRecommendRequest):
    """
    Generate recommendations from a raw sequence of product IDs.
    This is useful for anonymous users or when you want to get recommendations
    based on a specific browsing session rather than a stored user profile.
    """
    _ensure_model()
    recommendations = _recommend_from_sequence(
        product_ids=request.product_ids,
        top_k=request.top_k,
        exclude_input=request.exclude_input,
    )
    return RecommendResponse(
        user_id=0,  # No specific user
        recommendations=recommendations,
        model_version=API_VERSION,
    )


@app.post(
    "/recommend/similar",
    response_model=SimilarItemsResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Recommendations"],
    summary="Find similar products",
)
async def similar_items(request: SimilarItemsRequest):
    """
    Find products similar to a given product using embedding cosine similarity.
    This uses the learned item embeddings from the SASRec model to find
    products that are semantically close in the recommendation space.
    """
    _ensure_model()

    pid = request.product_id
    if pid not in state.item2idx:
        raise HTTPException(
            status_code=404,
            detail=f"Product {pid} is not known to the model.",
        )

    item_idx = state.item2idx[pid]

    # Get all item embeddings
    with torch.no_grad():
        all_embs = state.model.item_emb.weight.data  # (num_items, hidden_dim)
        target_emb = all_embs[item_idx].unsqueeze(0)  # (1, hidden_dim)

        # Cosine similarity
        norms = all_embs.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        target_norm = target_emb.norm(dim=-1, keepdim=True).clamp(min=1e-8)

        similarities = (all_embs / norms) @ (target_emb / target_norm).T
        similarities = similarities.squeeze(-1).cpu().numpy()

    # Sort and exclude padding (index 0) and the item itself
    item_scores = []
    for idx in range(1, len(similarities)):
        if idx == item_idx:
            continue
        orig_pid = state.idx2item.get(idx, idx)
        item_scores.append((orig_pid, float(similarities[idx])))

    item_scores.sort(key=lambda x: x[1], reverse=True)

    results = [
        _enrich_product(rank + 1, pid, score)
        for rank, (pid, score) in enumerate(item_scores[:request.top_k])
    ]

    return SimilarItemsResponse(
        product_id=pid,
        similar_items=results,
        model_version=API_VERSION,
    )


# ═══════════════════════════════════════════════════════════════
#  Run with: uvicorn api.main:app --reload --port 8000
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
