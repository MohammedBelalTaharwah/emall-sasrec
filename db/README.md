# 🗄️ E-Mall Database Schema

## Overview

This directory contains the version-controlled SQL Server schema for the E-Mall e-commerce platform.
All schema changes are managed through numbered migration files — **never edit the database directly.**

## Directory Structure

```
db/
├── migrations/          ← Numbered DDL scripts (append-only)
│   └── V001__initial_schema.sql
├── seeds/               ← Reference data and test fixtures
│   └── seed_categories.sql
└── README.md            ← This file
```

## How to Apply

### Local Development (first-time setup)

```bash
# Option 1: Docker (recommended)
docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=EMall@2026!" \
  -p 1433:1433 --name emall-db \
  -d mcr.microsoft.com/mssql/server:2022-latest

# Option 2: LocalDB (comes with Visual Studio)
# Already available — just create the database

# Then apply the schema:
sqlcmd -S localhost -U sa -P "EMall@2026!" -i db/migrations/V001__initial_schema.sql

# Then seed reference data:
sqlcmd -S localhost -U sa -P "EMall@2026!" -i db/seeds/seed_categories.sql
```

### Adding a Schema Change

1. **Never modify** an existing migration file
2. Create a new file: `V{NNN}__{description}.sql`
3. Open a Pull Request — both AI and backend teams must review changes to `Interactions`, `Recommendations`, or `ModelMetadata`
4. After merge, each developer applies the new migration to their local DB

## Naming Convention

```
V001__initial_schema.sql
V002__add_wishlist_table.sql
V003__add_interaction_weight.sql
```

- `V{NNN}` — Sequential version number, zero-padded
- `__` — Double underscore separator
- `{description}` — Snake_case description of the change

## AI-Specific Tables

Three tables in this schema are shared between the .NET backend and the SASRec AI service.
**Any changes to these tables require review from both teams.**

| Table | Written By | Read By |
|---|---|---|
| `Interactions` | .NET Backend | AI Service |
| `Recommendations` | AI Service | .NET Backend |
| `ModelMetadata` | AI Service | Both |

See [`docs/ai-integration.md`](../docs/ai-integration.md) for the full integration contract.
