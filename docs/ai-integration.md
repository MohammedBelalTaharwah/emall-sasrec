# E-Mall: AI ↔ Backend Integration Contract

## Overview

The E-Mall platform uses a **single SQL Server database** shared between two services:

| Service | Technology | Role |
|---|---|---|
| **E-Mall Backend** | ASP.NET Core + Entity Framework | Core e-commerce: users, products, orders, cart, payments |
| **SASRec AI Service** | Python, FastAPI, PyTorch | Sequential product recommendations using Transformer model |

This document defines the contract between these two systems.

---

## Architecture

```
┌──────────────────────┐         HTTP          ┌──────────────────────┐
│                      │  POST /recommend      │                      │
│   .NET Backend       │ ───────────────────►  │   SASRec AI Service  │
│   (ASP.NET Core)     │                       │   (FastAPI + PyTorch)│
│                      │  ◄─── JSON response   │                      │
│   Port: 5000/5001    │                       │   Port: 8000         │
└──────────┬───────────┘                       └──────────┬───────────┘
           │                                              │
           │  Writes: Interactions                        │  Reads: Interactions
           │  Reads:  Recommendations                     │  Writes: Recommendations
           │                                              │
           └──────────────┬───────────────────────────────┘
                          │
                   ┌──────▼──────┐
                   │  SQL Server │
                   │   Database  │
                   └─────────────┘
```

---

## Shared Tables

### 1. `Interactions` Table

**Writer:** .NET Backend  
**Reader:** AI Service  

This is the primary data source for the AI model. Every user action on the platform
must be logged here for the recommendation system to learn from.

#### Required Columns

| Column | Type | Description | Constraints |
|---|---|---|---|
| `InteractionId` | `BIGINT IDENTITY` | Primary key | Auto-increment |
| `UserId` | `INT` | Foreign key → Users | NOT NULL |
| `ProductId` | `INT` | Foreign key → Products | NOT NULL |
| `InteractionType` | `NVARCHAR(20)` | Action type | NOT NULL |
| `Timestamp` | `DATETIME2` | When the action occurred | NOT NULL, DEFAULT GETUTCDATE() |

#### Interaction Types

The AI model currently uses these interaction types (ordered by signal strength):

| Type | Signal | Description | AI Weight |
|---|---|---|---|
| `purchase` | 🟢 Strongest | User completed a purchase | Used for training |
| `add_to_cart` | 🟢 Strong | User added item to cart | Used for training |
| `click` | 🟡 Medium | User clicked on a product | Used for inference context |
| `view` | 🟠 Weak | User viewed a product page | Used for inference context |

> **Critical:** The AI training pipeline filters to `purchase` + `add_to_cart` only.
> All 4 types are used during inference to build the user's full interaction sequence.

#### .NET Implementation Requirements

```csharp
// The backend MUST log interactions in this exact format:
var interaction = new Interaction
{
    UserId = currentUser.Id,
    ProductId = product.Id,
    InteractionType = "purchase",  // exact lowercase string
    Timestamp = DateTime.UtcNow    // always UTC
};
await _context.Interactions.AddAsync(interaction);
```

#### Index Requirements (for AI query performance)

```sql
-- The AI service queries by user + time order
CREATE INDEX IX_Interactions_User_Time ON Interactions (UserId, Timestamp);

-- The AI service also aggregates by product
CREATE INDEX IX_Interactions_Product ON Interactions (ProductId);
```

---

### 2. `Recommendations` Table

**Writer:** AI Service (batch mode)  
**Reader:** .NET Backend  

Pre-computed recommendations stored for fast retrieval. Updated periodically
by the AI service (e.g., every 6 hours or after model retraining).

#### Required Columns

| Column | Type | Description |
|---|---|---|
| `RecommendationId` | `BIGINT IDENTITY` | Primary key |
| `UserId` | `INT` | Foreign key → Users |
| `ProductId` | `INT` | Recommended product |
| `Score` | `FLOAT` | Model confidence score (higher = more relevant) |
| `Rank` | `INT` | 1-based position in the recommendation list |
| `GeneratedAt` | `DATETIME2` | When this recommendation was generated |
| `ModelVersion` | `NVARCHAR(20)` | Version of the model that produced this |

#### .NET Usage

```csharp
// Get latest recommendations for a user
var recommendations = await _context.Recommendations
    .Where(r => r.UserId == userId)
    .OrderByDescending(r => r.GeneratedAt)
    .ThenBy(r => r.Rank)
    .Take(10)
    .Include(r => r.Product)
    .ToListAsync();
```

---

### 3. `ModelMetadata` Table

**Writer:** AI Service (after training)  
**Reader:** Both teams (monitoring)  

Tracks which model versions have been trained, their performance metrics,
and which version is currently active.

#### Required Columns

| Column | Type | Description |
|---|---|---|
| `ModelId` | `INT IDENTITY` | Primary key |
| `ModelVersion` | `NVARCHAR(20)` | Semantic version (e.g., "1.0.0") |
| `TrainedAt` | `DATETIME2` | When training completed |
| `TestHR10` | `FLOAT` | Test Hit Rate @ 10 |
| `TestNDCG10` | `FLOAT` | Test NDCG @ 10 |
| `NumItems` | `INT` | Number of items in the model |
| `NumUsers` | `INT` | Number of users in training data |
| `CheckpointPath` | `NVARCHAR(500)` | Path to the `.pth` file |
| `IsActive` | `BIT` | Whether this is the currently served model |

---

## API Endpoints (SASRec Service)

The .NET backend communicates with the AI service via HTTP.
Base URL: `http://localhost:8000` (dev) or configured via environment variable.

| Method | Endpoint | Purpose | When to Use |
|---|---|---|---|
| `GET` | `/health` | Check if AI service is running | Startup health check |
| `POST` | `/recommend` | Get recommendations for 1 user | Product page, "You might like" |
| `POST` | `/recommend/batch` | Get recommendations for many users | Email campaigns, push notifications |
| `POST` | `/recommend/sequence` | Recommendations from a browsing session | Anonymous users, guest checkout |
| `POST` | `/recommend/similar` | Find similar products | "Similar products" section |

### Example .NET HTTP Client

```csharp
// In your .NET service
public class RecommendationService
{
    private readonly HttpClient _httpClient;

    public RecommendationService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("SASRec");
    }

    public async Task<RecommendResponse> GetRecommendationsAsync(int userId, int topK = 10)
    {
        var request = new { user_id = userId, top_k = topK, exclude_interacted = true };
        var response = await _httpClient.PostAsJsonAsync("/recommend", request);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<RecommendResponse>();
    }
}

// In Program.cs / Startup.cs
builder.Services.AddHttpClient("SASRec", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["AI:SASRecUrl"] ?? "http://localhost:8000");
    client.Timeout = TimeSpan.FromSeconds(10);
});
```

---

## Change Management Rules

1. **Any PR that modifies the `Interactions`, `Recommendations`, or `ModelMetadata` table must be reviewed by both teams**
2. **Column additions** are generally safe — coordinate on defaults
3. **Column removals or renames** require a joint migration plan
4. **InteractionType values** — adding new types is fine; renaming existing ones breaks the AI pipeline
5. **Always use UTC timestamps** — the AI model relies on chronological ordering
