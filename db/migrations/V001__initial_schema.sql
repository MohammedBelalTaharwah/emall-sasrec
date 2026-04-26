-- ============================================================
-- V001__initial_schema.sql
-- E-Mall Database Schema v1.0 — AI Service Tables
-- Generated from ERD on 2026-04-26
-- ============================================================
-- 
-- This migration creates the tables needed by the SASRec AI
-- recommendation service + the minimal parent tables (Users,
-- Products, Categories) required for foreign key integrity.
--
-- The .NET backend team will ADD their own tables (Orders,
-- Cart, Wishlist, etc.) in subsequent migrations.
--
-- HOW TO APPLY:
--   sqlcmd -S localhost -U sa -P "YourPassword" -i db/migrations/V001__initial_schema.sql
--
-- IMPORTANT: Do NOT modify this file after it has been applied.
--            Create a new V002__*.sql file for any schema changes.
-- ============================================================

USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'EMall')
BEGIN
    CREATE DATABASE [EMall];
END
GO

USE [EMall];
GO

-- ════════════════════════════════════════════════════════════
-- PARENT TABLES (minimal — backend team extends these later)
-- ════════════════════════════════════════════════════════════

-- ── 1. Categories ──────────────────────────────────────────
CREATE TABLE [dbo].[Categories] (
    [CategoryId]        INT             IDENTITY(1,1) PRIMARY KEY,
    [CategoryName]      NVARCHAR(100)   NOT NULL,
    [Description]       NVARCHAR(500)   NULL,
    [ParentCategoryId]  INT             NULL REFERENCES [dbo].[Categories]([CategoryId]),
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_Categories_Name UNIQUE ([CategoryName])
);
GO

-- ── 2. Users (minimal — backend adds Email, PasswordHash, etc.) ──
CREATE TABLE [dbo].[Users] (
    [UserId]            INT             IDENTITY(1,1) PRIMARY KEY,
    [FullName]          NVARCHAR(200)   NOT NULL,
    [AgeGroup]          NVARCHAR(10)    NULL,       -- '18-24', '25-34', '35-44', '45-54', '55+'
    [Gender]            NVARCHAR(10)    NULL,       -- 'M', 'F', 'Other'
    [City]              NVARCHAR(100)   NULL,
    [IsActive]          BIT             NOT NULL DEFAULT 1,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
);
GO

-- ── 3. Products (minimal — backend adds stock, images, etc.) ──
CREATE TABLE [dbo].[Products] (
    [ProductId]         INT             IDENTITY(1,1) PRIMARY KEY,
    [ProductName]       NVARCHAR(300)   NOT NULL,
    [CategoryId]        INT             NOT NULL REFERENCES [dbo].[Categories]([CategoryId]),
    [Subcategory]       NVARCHAR(100)   NULL,
    [Brand]             NVARCHAR(100)   NULL,
    [Price]             DECIMAL(18,2)   NOT NULL,
    [IsActive]          BIT             NOT NULL DEFAULT 1,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
);
GO


-- ════════════════════════════════════════════════════════════
-- AI-SPECIFIC TABLES (SASRec Service)
-- ════════════════════════════════════════════════════════════
-- ⚠️  Any schema changes to these 3 tables require review
--     from BOTH the AI and Backend teams.
--     See: docs/ai-integration.md
-- ════════════════════════════════════════════════════════════

-- ── 4. Interactions ────────────────────────────────────────
-- Every user action on the platform is logged here.
-- This is the PRIMARY data source for the AI model.
--
-- Written by: .NET Backend
-- Read by:    AI Service (training + inference)
CREATE TABLE [dbo].[Interactions] (
    [InteractionId]     BIGINT          IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [InteractionType]   NVARCHAR(20)    NOT NULL,
                                        -- 'view'         → weak signal
                                        -- 'click'        → medium signal
                                        -- 'add_to_cart'  → strong signal
                                        -- 'purchase'     → strongest signal
    [Timestamp]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
);
GO

-- AI reads: user interaction history ordered by time
CREATE NONCLUSTERED INDEX IX_Interactions_User_Time
    ON [dbo].[Interactions] ([UserId], [Timestamp]);
GO

-- AI reads: aggregate stats by product
CREATE NONCLUSTERED INDEX IX_Interactions_Product
    ON [dbo].[Interactions] ([ProductId]);
GO

-- AI reads: filter by type (training uses purchase + add_to_cart only)
CREATE NONCLUSTERED INDEX IX_Interactions_Type
    ON [dbo].[Interactions] ([InteractionType]);
GO


-- ── 5. Recommendations ────────────────────────────────────
-- Pre-computed recommendations from the AI service.
--
-- Written by: AI Service (batch mode)
-- Read by:    .NET Backend (display to users)
CREATE TABLE [dbo].[Recommendations] (
    [RecommendationId]  BIGINT          IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [Score]             FLOAT           NOT NULL,
    [Rank]              INT             NOT NULL,
    [GeneratedAt]       DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [ModelVersion]      NVARCHAR(20)    NOT NULL DEFAULT '1.0.0',
);
GO

CREATE NONCLUSTERED INDEX IX_Recommendations_User
    ON [dbo].[Recommendations] ([UserId], [GeneratedAt] DESC);
GO


-- ── 6. ModelMetadata ───────────────────────────────────────
-- Tracks AI model versions and performance metrics.
--
-- Written by: AI Service (after training)
-- Read by:    Both teams (monitoring)
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
GO


-- ════════════════════════════════════════════════════════════
-- SUMMARY: 6 tables
--   Parents:  Categories, Users, Products (minimal)
--   AI:       Interactions, Recommendations, ModelMetadata
--
-- Backend team: add your tables (Orders, Cart, Wishlist, etc.)
-- in V002__*.sql migrations.
-- ════════════════════════════════════════════════════════════

PRINT '✅ E-Mall AI schema V001 applied — 6 tables created';
GO
