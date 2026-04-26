"""
E-Mall SASRec API — Pydantic Schemas
======================================
Request and response models for the recommendation endpoints.
Provides type-safe contracts between the .NET backend and the Python AI service.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ═══════════════════════════════════════════════════════════════
#  Request Models
# ═══════════════════════════════════════════════════════════════

class RecommendRequest(BaseModel):
    """Request body for single-user recommendation."""
    user_id: int = Field(..., description="The user ID to generate recommendations for.", ge=1)
    top_k: int = Field(10, description="Number of recommendations to return.", ge=1, le=50)
    exclude_interacted: bool = Field(
        True,
        description="If true, exclude items the user has already interacted with."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 42,
                "top_k": 10,
                "exclude_interacted": True,
            }
        }


class BatchRecommendRequest(BaseModel):
    """Request body for batch user recommendations."""
    user_ids: list[int] = Field(..., description="List of user IDs.", min_length=1, max_length=100)
    top_k: int = Field(10, description="Number of recommendations per user.", ge=1, le=50)
    exclude_interacted: bool = Field(True, description="Exclude already-interacted items.")

    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": [1, 42, 100],
                "top_k": 5,
                "exclude_interacted": True,
            }
        }


class SimilarItemsRequest(BaseModel):
    """Request body for similar-items lookup."""
    product_id: int = Field(..., description="The product ID to find similar items for.", ge=1)
    top_k: int = Field(10, description="Number of similar items to return.", ge=1, le=50)

    class Config:
        json_schema_extra = {
            "example": {
                "product_id": 5,
                "top_k": 10,
            }
        }


class SequenceRecommendRequest(BaseModel):
    """Request body for recommendation from a raw item sequence (no user_id needed)."""
    product_ids: list[int] = Field(
        ...,
        description="Chronological list of product IDs the user has interacted with.",
        min_length=1,
    )
    top_k: int = Field(10, description="Number of recommendations to return.", ge=1, le=50)
    exclude_input: bool = Field(True, description="Exclude the input items from recommendations.")

    class Config:
        json_schema_extra = {
            "example": {
                "product_ids": [5, 42, 100, 7, 250],
                "top_k": 10,
                "exclude_input": True,
            }
        }


# ═══════════════════════════════════════════════════════════════
#  Response Models
# ═══════════════════════════════════════════════════════════════

class RecommendedProduct(BaseModel):
    """A single recommended product with its score and metadata."""
    rank: int = Field(..., description="1-based rank position.")
    product_id: int = Field(..., description="The original product ID from the database.")
    score: float = Field(..., description="The model's confidence score (higher = more relevant).")
    product_name: Optional[str] = Field(None, description="Product name (if product metadata is loaded).")
    category: Optional[str] = Field(None, description="Product category.")
    price: Optional[float] = Field(None, description="Product price.")
    image_url: Optional[str] = Field(None, description="Product image URL.")


class RecommendResponse(BaseModel):
    """Response for a single-user recommendation request."""
    user_id: int
    recommendations: list[RecommendedProduct]
    model_version: str = "1.0.0"


class BatchRecommendResponse(BaseModel):
    """Response for batch recommendation requests."""
    results: list[RecommendResponse]
    model_version: str = "1.0.0"


class SimilarItemsResponse(BaseModel):
    """Response for similar-items lookup."""
    product_id: int
    similar_items: list[RecommendedProduct]
    model_version: str = "1.0.0"


class HealthResponse(BaseModel):
    """Response for health check endpoint."""
    status: str
    model_loaded: bool
    num_items: int
    num_users: int
    device: str
    model_version: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str
