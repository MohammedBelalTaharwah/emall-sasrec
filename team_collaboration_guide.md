# E-Mall: Database & AI Collaboration Guide

## Your Situation

You have:
- A **finalized ERD** for the E-Mall e-commerce platform (SQL Server)
- A **working SASRec AI service** (Python/FastAPI) that depends on 3 entities from the schema
- A **.NET backend team** that needs to build the platform on top of this same database

The core question: *How does the AI architecture and this database get managed collaboratively?*

---

## TL;DR Recommendation

**Do all three — but in the right order:**

| Approach | Verdict | Why |
|---|---|---|
| Export SQL DDL scripts to GitHub | ✅ **Yes — do this first** | The ERD becomes the single source of truth; version-controlled and reviewable |
| Shared cloud database | ✅ **Yes — but not for development** | Use for staging/integration testing only; each dev runs their own local instance |
| ORM recreation from ERD | ✅ **Yes — this is how the .NET team builds** | Entity Framework Core models are generated *from* or *validated against* the DDL |

> [!IMPORTANT]
> The critical principle: **The DDL scripts in Git are the canonical schema.** The ORM models are derived from them, not the other way around.

---

## Architecture Overview

```mermaid
graph TB
    subgraph "Git Repository (Single Source of Truth)"
        DDL["📄 SQL DDL Scripts<br/>db/migrations/"]
        SEED["📄 Seed Data Scripts<br/>db/seeds/"]
        ERD["📄 ERD Diagram<br/>docs/erd.png"]
    end

    subgraph ".NET Backend Team"
        EF["Entity Framework Core<br/>Code-First Models"]
        DOTNET["ASP.NET Core API<br/>Controllers, Services"]
    end

    subgraph "AI Team (You)"
        SASREC["SASRec FastAPI Service<br/>Python, PyTorch"]
        TRAIN["Training Pipeline<br/>train_and_save.py"]
    end

    subgraph "SQL Server Database"
        PLATFORM["Platform Tables<br/>Users, Products, Orders,<br/>Categories, Cart, etc."]
        AI_TABLES["AI Tables<br/>Interactions,<br/>Recommendations,<br/>ModelMetadata"]
    end

    DDL -->|"migrations applied"| PLATFORM
    DDL -->|"migrations applied"| AI_TABLES
    EF -->|"reads/writes"| PLATFORM
    EF -->|"writes interactions"| AI_TABLES
    SASREC -->|"reads interactions"| AI_TABLES
    SASREC -->|"writes recommendations"| AI_TABLES
    DOTNET --> EF
    DOTNET -->|"HTTP calls"| SASREC
```

---

## Step-by-Step Workflow

### Phase 1: Schema as Code (You — Before Handoff)

This is the foundational step. You export the ERD into version-controlled SQL scripts.

#### Step 1.1 — Export the DDL from your ERD

Using SQL Server Management Studio (SSMS) or your ERD tool, generate the full `CREATE TABLE` scripts. Organize them in the repository like this:

```
GP-02/
├── db/
│   ├── migrations/
│   │   └── V001__initial_schema.sql      ← Full DDL: all tables, PKs, FKs, indexes
│   ├── seeds/
│   │   ├── seed_categories.sql           ← Reference/lookup data
│   │   └── seed_test_users.sql           ← Dev/test data
│   └── README.md                         ← Schema documentation
├── src/
│   ├── EMall.API/                        ← .NET backend (team builds this)
│   └── EMall.AI/                         ← Your AI service (api/ folder, renamed)
└── docs/
    ├── erd.png                           ← Your ERD diagram (high-res)
    └── ai-integration.md                 ← API contract documentation
```

#### Step 1.2 — Write the DDL Script

The migration file should look like this (example structure based on your ERD):

```sql
-- V001__initial_schema.sql
-- E-Mall Database Schema v1.0
-- Generated from ERD on 2026-04-26
-- ============================================================

-- ── Core Platform Tables ────────────────────────────────────

CREATE TABLE [dbo].[Users] (
    [UserId]        INT             IDENTITY(1,1) PRIMARY KEY,
    [Email]         NVARCHAR(255)   NOT NULL UNIQUE,
    [PasswordHash]  NVARCHAR(512)   NOT NULL,
    [FullName]      NVARCHAR(200)   NOT NULL,
    [PhoneNumber]   NVARCHAR(20)    NULL,
    [CreatedAt]     DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [UpdatedAt]     DATETIME2       NULL,
    -- ... other columns from your ERD
);

CREATE TABLE [dbo].[Categories] (
    [CategoryId]    INT             IDENTITY(1,1) PRIMARY KEY,
    [CategoryName]  NVARCHAR(100)   NOT NULL,
    [ParentCategoryId] INT          NULL REFERENCES [dbo].[Categories]([CategoryId]),
    -- ...
);

CREATE TABLE [dbo].[Products] (
    [ProductId]     INT             IDENTITY(1,1) PRIMARY KEY,
    [ProductName]   NVARCHAR(300)   NOT NULL,
    [CategoryId]    INT             NOT NULL REFERENCES [dbo].[Categories]([CategoryId]),
    [Price]         DECIMAL(18,2)   NOT NULL,
    [ImageUrl]      NVARCHAR(500)   NULL,
    [CreatedAt]     DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    -- ...
);

-- ── AI-Specific Tables (Shared with SASRec Service) ─────────

CREATE TABLE [dbo].[Interactions] (
    [InteractionId]     BIGINT          IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [InteractionType]   NVARCHAR(20)    NOT NULL,  -- view, click, add_to_cart, purchase
    [Timestamp]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    INDEX IX_Interactions_User_Time ([UserId], [Timestamp]),
    INDEX IX_Interactions_Product   ([ProductId]),
    INDEX IX_Interactions_Type      ([InteractionType]),
);

CREATE TABLE [dbo].[Recommendations] (
    [RecommendationId]  BIGINT          IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [Score]             FLOAT           NOT NULL,
    [Rank]              INT             NOT NULL,
    [GeneratedAt]       DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [ModelVersion]      NVARCHAR(20)    NOT NULL DEFAULT '1.0.0',

    INDEX IX_Recommendations_User ([UserId], [GeneratedAt] DESC),
);

CREATE TABLE [dbo].[ModelMetadata] (
    [ModelId]           INT             IDENTITY(1,1) PRIMARY KEY,
    [ModelVersion]      NVARCHAR(20)    NOT NULL,
    [TrainedAt]         DATETIME2       NOT NULL,
    [TestHR10]          FLOAT           NULL,
    [TestNDCG10]        FLOAT           NULL,
    [NumItems]          INT             NOT NULL,
    [NumUsers]          INT             NOT NULL,
    [CheckpointPath]    NVARCHAR(500)   NULL,
    [IsActive]          BIT             NOT NULL DEFAULT 1,
);
```

> [!NOTE]
> The exact column names and types should come from your actual ERD. The structure above is illustrative based on what I can infer from your ERD image and the existing CSV/API schemas.

#### Step 1.3 — Push to GitHub

```bash
git add db/ docs/
git commit -m "feat(db): add initial schema DDL from ERD v1.0

- Full platform schema: Users, Products, Categories, Orders, Cart, etc.
- AI integration tables: Interactions, Recommendations, ModelMetadata
- Indexes optimized for AI query patterns (user+timestamp, product)"
git push origin main
```

---

### Phase 2: .NET Team Onboarding (Backend Team)

#### Step 2.1 — Database-First or Code-First?

For your situation, I recommend **Code-First with DDL validation**:

```mermaid
graph LR
    A["Your DDL Scripts<br/>(source of truth)"] --> B["Team reads DDL"]
    B --> C["Team writes EF Core<br/>entity classes"]
    C --> D["EF generates migration"]
    D --> E["Compare with your DDL"]
    E -->|"Match ✅"| F["Apply to local DB"]
    E -->|"Mismatch ❌"| C
```

The .NET team:

1. **Reads your DDL scripts** in `db/migrations/`
2. **Creates Entity Framework Core models** that match your schema exactly
3. **Uses EF migrations** going forward for incremental changes
4. **Validates** that their generated migration output matches your DDL

Example EF Core entity matching your `Interactions` table:

```csharp
// EMall.API/Models/Interaction.cs
public class Interaction
{
    public long InteractionId { get; set; }
    public int UserId { get; set; }
    public int ProductId { get; set; }
    public string InteractionType { get; set; }  // "view", "click", "add_to_cart", "purchase"
    public DateTime Timestamp { get; set; }

    // Navigation properties
    public User User { get; set; }
    public Product Product { get; set; }
}
```

#### Step 2.2 — Each Developer Gets a Local Database

> [!WARNING]
> **Do NOT develop directly against a shared database.** This is the #1 source of team conflicts in database-backed projects.

Each developer runs their own local SQL Server instance:

| Tool | Purpose |
|---|---|
| **SQL Server Developer Edition** (free) | Full-featured local instance |
| **SQL Server in Docker** | Lightweight, reproducible |
| **LocalDB** (comes with Visual Studio) | Simplest option for .NET devs |

Setup script for Docker (one command):

```bash
docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=YourStrong!Passw0rd" \
  -p 1433:1433 --name emall-db \
  -d mcr.microsoft.com/mssql/server:2022-latest
```

Then apply the migration:

```bash
sqlcmd -S localhost -U sa -P "YourStrong!Passw0rd" -i db/migrations/V001__initial_schema.sql
```

---

### Phase 3: Shared Environments (Staging Only)

Set up shared databases **only** for integration testing:

```mermaid
graph TB
    subgraph "Developer Machines"
        D1["Dev 1<br/>Local SQL Server"]
        D2["Dev 2<br/>Local SQL Server"]
        D3["You (AI)<br/>Local SQL Server"]
    end

    subgraph "Azure / Cloud"
        STAGING["Staging DB<br/>(Azure SQL / shared server)"]
        PROD["Production DB<br/>(Azure SQL / VPS)"]
    end

    D1 -->|"PR merged → CI/CD"| STAGING
    D2 -->|"PR merged → CI/CD"| STAGING
    D3 -->|"PR merged → CI/CD"| STAGING
    STAGING -->|"Release"| PROD
```

> [!TIP]
> For a graduation project, a simple Azure SQL free tier or a VPS with SQL Server Express is sufficient for staging. You don't need complex cloud infrastructure.

---

### Phase 4: Schema Change Workflow (Ongoing)

Once the initial schema is in place, all future changes follow this Git-based workflow:

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Git as GitHub (PR)
    participant Review as Team Review
    participant DB as Database

    Dev->>Git: Create branch: feature/add-wishlist-table
    Dev->>Git: Add V002__add_wishlist.sql
    Dev->>Git: Update EF Core models
    Dev->>Git: Open Pull Request
    Git->>Review: AI team reviews (does this affect Interactions?)
    Git->>Review: Backend team reviews (EF models correct?)
    Review->>Git: Approve & merge
    Git->>DB: CI/CD applies migration to staging
```

#### Migration Naming Convention

```
db/migrations/
├── V001__initial_schema.sql
├── V002__add_wishlist_table.sql
├── V003__add_interaction_weight_column.sql
├── V004__add_product_description_fulltext.sql
```

#### Rules for Schema Changes

| Rule | Why |
|---|---|
| **Never modify a released migration** | Other environments have already applied it |
| **Always add new migration files** | Append-only; the history is sacred |
| **Tag AI-related changes explicitly** | So you can review anything touching your 3 tables |
| **No direct DB edits in staging/prod** | All changes go through Git → migration → apply |

---

### Phase 5: AI ↔ .NET Integration Contract

This is the critical piece — how your SASRec service and the .NET backend coexist.

#### 5.1 — Data Flow

```mermaid
graph LR
    subgraph ".NET Backend"
        A["User browses/buys"] --> B["Write to Interactions table"]
        F["Read from Recommendations"] --> G["Display to user"]
    end

    subgraph "SASRec AI Service"
        C["Read from Interactions"] --> D["Generate recommendations"]
        D --> E["Write to Recommendations table<br/>(or return via HTTP)"]
    end

    B --> C
    E --> F
```

#### 5.2 — Two Integration Modes

Your current architecture supports both — use them for different scenarios:

**Mode A — Synchronous HTTP (Real-time)**
```
User opens product page
  → .NET backend calls POST /recommend to SASRec API
  → SASRec returns top-K recommendations
  → .NET displays them immediately
```
*Already implemented in your FastAPI service. Good for real-time personalization.*

**Mode B — Batch Database Write (Periodic)**
```
Scheduled job (every 6 hours)
  → SASRec reads all recent Interactions from DB
  → Generates recommendations for active users
  → Writes results to Recommendations table
  → .NET reads from Recommendations table (fast, no HTTP call)
```
*Better for homepage "Recommended for You" sections where freshness isn't critical.*

#### 5.3 — Your AI Service Connection

Your current AI service reads from CSV files. For production, update `config.py` to support both modes:

```python
# config.py — add database connection option
import os

# Database mode: "csv" for development, "database" for production
DATA_SOURCE = os.getenv("DATA_SOURCE", "csv")

# SQL Server connection (production)
DB_CONNECTION_STRING = os.getenv(
    "DB_CONNECTION_STRING",
    "mssql+pyodbc://sa:YourPassword@localhost/EMall?driver=ODBC+Driver+18+for+SQL+Server"
)
```

> [!NOTE]
> You don't need to change this now. Keep reading CSVs during development. Switch to database reads when the .NET team has the platform running and generating real interactions.

---

### Phase 6: The 3 AI Tables — Ownership Rules

Based on your ERD, the three AI-specific entities and their ownership:

| Table | Written By | Read By | Owner |
|---|---|---|---|
| **Interactions** | .NET Backend (logs user actions) | AI Service (training + inference) | .NET team owns writes; AI team owns the read patterns |
| **Recommendations** | AI Service (batch results) | .NET Backend (display to users) | AI team owns writes; .NET team owns the read patterns |
| **ModelMetadata** | AI Service (after training) | Both (monitoring, version display) | AI team |

> [!IMPORTANT]
> **Golden Rule:** If a schema change to any of these 3 tables is proposed, **both teams must review the PR.** Use GitHub's CODEOWNERS file to enforce this:
>
> ```
> # .github/CODEOWNERS
> db/migrations/*interaction*    @ai-team @backend-team
> db/migrations/*recommendation* @ai-team @backend-team
> db/migrations/*model*          @ai-team
> ```

---

## Concrete Handoff Checklist

Here's your actionable checklist for the handoff:

### You Do (This Week)
- [ ] Export high-resolution ERD as PNG and PDF → `docs/erd.png`
- [ ] Write `V001__initial_schema.sql` from the ERD → `db/migrations/`
- [ ] Write `db/README.md` documenting every table's purpose
- [ ] Create seed scripts for categories and test data → `db/seeds/`
- [ ] Document the 3 AI tables and their contracts in `docs/ai-integration.md`
- [ ] Push everything to GitHub
- [ ] Set up CODEOWNERS for the AI tables

### .NET Team Does (Next Week)
- [ ] Pull the repo; review the DDL and ERD
- [ ] Set up local SQL Server (Docker or LocalDB)
- [ ] Apply `V001__initial_schema.sql` to local instance
- [ ] Create EF Core models matching the schema
- [ ] Generate initial EF migration; verify it matches the DDL
- [ ] Build the first CRUD endpoints (Products, Categories)
- [ ] Implement the Interaction logging middleware

### Together (Week After)
- [ ] Verify the .NET app writes Interactions in the correct format
- [ ] Test the SASRec API reading from the shared staging database
- [ ] Run an end-to-end flow: browse → interact → recommend → display
- [ ] Set up a staging database and CI/CD pipeline for migrations

---

## Quick Reference: Answering Your Three Questions

### "Should I export SQL DDL scripts and push to GitHub?"
**Yes, absolutely.** This is the standard industry practice. The DDL scripts become versioned, reviewable, and the single source of truth for the schema. Your team can review changes via pull requests, and you have a complete history of every schema evolution.

### "Should we set up a shared cloud database?"
**Yes, but only for staging/integration testing.** During development, each team member should run their own local SQL Server instance. A shared database during active development leads to conflicts, broken migrations, and blocked developers. Set up the shared instance on Azure SQL (free tier) or a simple VPS for integration testing after features are PR-merged.

### "Should they recreate the schema using an ORM based on my ERD?"
**Yes, this is how they'll build the application.** But the ORM models should be *derived from* your DDL, not created independently. The workflow is: your DDL defines the truth → the team writes EF Core entities to match → EF migrations validate the match. This avoids drift between what you designed and what the ORM generates.

---

## Summary

The standard industry workflow is a **DDL-first, Git-managed, locally-developed** approach:

1. **You** export the schema as SQL DDL scripts into Git
2. **Each developer** runs a local SQL Server instance
3. **EF Core models** are written to match the DDL (not the other way around)
4. **Schema changes** go through Git PRs with mandatory review for shared tables
5. **Staging/production** databases are updated via CI/CD applying migration scripts
6. **AI and .NET** coexist on one database, with clear ownership boundaries per table
