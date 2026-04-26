-- ============================================================
-- V001__initial_schema.sql
-- E-Mall Database Schema v1.0
-- Generated from ERD on 2026-04-26
-- ============================================================
-- 
-- This is the INITIAL schema for the E-Mall e-commerce platform.
-- It creates ALL tables needed by both the .NET backend and the
-- SASRec AI recommendation service.
--
-- HOW TO APPLY:
--   sqlcmd -S localhost -U sa -P "YourPassword" -i db/migrations/V001__initial_schema.sql
--
-- IMPORTANT: Do NOT modify this file after it has been applied.
--            Create a new V002__*.sql file for any schema changes.
-- ============================================================

USE master;
GO

-- Create the database if it doesn't exist
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'EMall')
BEGIN
    CREATE DATABASE [EMall];
END
GO

USE [EMall];
GO

-- ════════════════════════════════════════════════════════════
-- CORE PLATFORM TABLES
-- ════════════════════════════════════════════════════════════

-- ── 1. Categories ──────────────────────────────────────────
-- Lookup table for product categories.
-- Data sourced from: categories.csv (10 rows)
-- Owner: .NET Backend
CREATE TABLE [dbo].[Categories] (
    [CategoryId]        INT             IDENTITY(1,1) PRIMARY KEY,
    [CategoryName]      NVARCHAR(100)   NOT NULL,
    [Description]       NVARCHAR(500)   NULL,
    [ParentCategoryId]  INT             NULL REFERENCES [dbo].[Categories]([CategoryId]),
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [UpdatedAt]         DATETIME2       NULL,

    CONSTRAINT UQ_Categories_Name UNIQUE ([CategoryName])
);
GO

-- ── 2. Users ───────────────────────────────────────────────
-- Platform user accounts.
-- Data sourced from: users.csv (10,000 rows)
-- Columns: user_id, age_group, gender, city, registration_date, is_active
-- Owner: .NET Backend
CREATE TABLE [dbo].[Users] (
    [UserId]            INT             IDENTITY(1,1) PRIMARY KEY,
    [Email]             NVARCHAR(255)   NOT NULL UNIQUE,
    [PasswordHash]      NVARCHAR(512)   NOT NULL,
    [FullName]          NVARCHAR(200)   NOT NULL,
    [PhoneNumber]       NVARCHAR(20)    NULL,
    [AgeGroup]          NVARCHAR(10)    NULL,       -- '18-24', '25-34', '35-44', '45-54', '55+'
    [Gender]            NVARCHAR(10)    NULL,       -- 'M', 'F', 'Other'
    [City]              NVARCHAR(100)   NULL,       -- 'Amman', 'Irbid', 'Zarqa', etc.
    [IsActive]          BIT             NOT NULL DEFAULT 1,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [UpdatedAt]         DATETIME2       NULL,
);
GO

-- ── 3. Products ────────────────────────────────────────────
-- Product catalog.
-- Data sourced from: products.csv (1,000 rows)
-- Columns: product_id, product_name, category, subcategory, brand,
--          price, original_price, rating, review_count, description,
--          image_url, stock_quantity, is_active
-- Owner: .NET Backend
CREATE TABLE [dbo].[Products] (
    [ProductId]         INT             IDENTITY(1,1) PRIMARY KEY,
    [ProductName]       NVARCHAR(300)   NOT NULL,
    [CategoryId]        INT             NOT NULL REFERENCES [dbo].[Categories]([CategoryId]),
    [Subcategory]       NVARCHAR(100)   NULL,
    [Brand]             NVARCHAR(100)   NULL,
    [Price]             DECIMAL(18,2)   NOT NULL,
    [OriginalPrice]     DECIMAL(18,2)   NULL,
    [Rating]            DECIMAL(3,1)    NULL DEFAULT 0,
    [ReviewCount]       INT             NULL DEFAULT 0,
    [Description]       NVARCHAR(MAX)   NULL,
    [ImageUrl]          NVARCHAR(500)   NULL,
    [StockQuantity]     INT             NOT NULL DEFAULT 0,
    [IsActive]          BIT             NOT NULL DEFAULT 1,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [UpdatedAt]         DATETIME2       NULL,
);
GO

-- ── 4. Addresses ───────────────────────────────────────────
-- User shipping/billing addresses.
-- Owner: .NET Backend
CREATE TABLE [dbo].[Addresses] (
    [AddressId]         INT             IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [FullName]          NVARCHAR(200)   NOT NULL,
    [PhoneNumber]       NVARCHAR(20)    NOT NULL,
    [AddressLine1]      NVARCHAR(300)   NOT NULL,
    [AddressLine2]      NVARCHAR(300)   NULL,
    [City]              NVARCHAR(100)   NOT NULL,
    [Country]           NVARCHAR(100)   NOT NULL DEFAULT 'Jordan',
    [PostalCode]        NVARCHAR(20)    NULL,
    [IsDefault]         BIT             NOT NULL DEFAULT 0,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
);
GO

-- ── 5. Orders ──────────────────────────────────────────────
-- Customer orders.
-- Owner: .NET Backend
CREATE TABLE [dbo].[Orders] (
    [OrderId]           INT             IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [AddressId]         INT             NULL REFERENCES [dbo].[Addresses]([AddressId]),
    [OrderStatus]       NVARCHAR(20)    NOT NULL DEFAULT 'pending',
                                        -- pending, confirmed, shipped, delivered, cancelled
    [TotalAmount]       DECIMAL(18,2)   NOT NULL,
    [ShippingCost]      DECIMAL(18,2)   NOT NULL DEFAULT 0,
    [PaymentMethod]     NVARCHAR(50)    NULL,       -- cash_on_delivery, credit_card, etc.
    [PaymentStatus]     NVARCHAR(20)    NOT NULL DEFAULT 'pending',
                                        -- pending, paid, failed, refunded
    [Notes]             NVARCHAR(500)   NULL,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [UpdatedAt]         DATETIME2       NULL,
);
GO

-- ── 6. OrderItems ──────────────────────────────────────────
-- Individual items within an order.
-- Owner: .NET Backend
CREATE TABLE [dbo].[OrderItems] (
    [OrderItemId]       INT             IDENTITY(1,1) PRIMARY KEY,
    [OrderId]           INT             NOT NULL REFERENCES [dbo].[Orders]([OrderId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [Quantity]          INT             NOT NULL DEFAULT 1,
    [UnitPrice]         DECIMAL(18,2)   NOT NULL,
    [TotalPrice]        DECIMAL(18,2)   NOT NULL,
);
GO

-- ── 7. Cart ────────────────────────────────────────────────
-- Shopping cart items (session-based or user-based).
-- Owner: .NET Backend
CREATE TABLE [dbo].[CartItems] (
    [CartItemId]        INT             IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [Quantity]          INT             NOT NULL DEFAULT 1,
    [AddedAt]           DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_Cart_User_Product UNIQUE ([UserId], [ProductId])
);
GO

-- ── 8. Wishlist ────────────────────────────────────────────
-- User wishlisted products.
-- Owner: .NET Backend
CREATE TABLE [dbo].[WishlistItems] (
    [WishlistItemId]    INT             IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [AddedAt]           DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_Wishlist_User_Product UNIQUE ([UserId], [ProductId])
);
GO

-- ── 9. ProductReviews ──────────────────────────────────────
-- User reviews and ratings for products.
-- Owner: .NET Backend
CREATE TABLE [dbo].[ProductReviews] (
    [ReviewId]          INT             IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [Rating]            INT             NOT NULL CHECK ([Rating] BETWEEN 1 AND 5),
    [ReviewText]        NVARCHAR(MAX)   NULL,
    [CreatedAt]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_Review_User_Product UNIQUE ([UserId], [ProductId])
);
GO


-- ════════════════════════════════════════════════════════════
-- AI-SPECIFIC TABLES (Shared with SASRec Service)
-- ════════════════════════════════════════════════════════════
-- ⚠️  IMPORTANT: Any schema changes to these 3 tables
--     require review from BOTH the AI and Backend teams.
--     See: docs/ai-integration.md
-- ════════════════════════════════════════════════════════════

-- ── 10. Interactions ───────────────────────────────────────
-- Every user action on the platform is logged here.
-- This is the PRIMARY data source for the AI recommendation model.
-- Data sourced from: interactions.csv (961,369 rows)
-- Columns: interaction_id, user_id, product_id, interaction_type, timestamp
--
-- Written by: .NET Backend (logs user actions)
-- Read by:    AI Service (training + inference)
CREATE TABLE [dbo].[Interactions] (
    [InteractionId]     BIGINT          IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [InteractionType]   NVARCHAR(20)    NOT NULL,
                                        -- 'view'         → user viewed product page (weak signal)
                                        -- 'click'        → user clicked on product (medium signal)
                                        -- 'add_to_cart'  → user added to cart (strong signal)
                                        -- 'purchase'     → user completed purchase (strongest signal)
    [Timestamp]         DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
);
GO

-- AI query patterns: user's interaction history ordered by time
CREATE NONCLUSTERED INDEX IX_Interactions_User_Time
    ON [dbo].[Interactions] ([UserId], [Timestamp]);
GO

-- AI query patterns: aggregate statistics by product
CREATE NONCLUSTERED INDEX IX_Interactions_Product
    ON [dbo].[Interactions] ([ProductId]);
GO

-- AI query patterns: filter by interaction type (training uses purchase + add_to_cart only)
CREATE NONCLUSTERED INDEX IX_Interactions_Type
    ON [dbo].[Interactions] ([InteractionType]);
GO


-- ── 11. Recommendations ────────────────────────────────────
-- Pre-computed recommendations generated by the AI service.
-- Updated periodically (e.g., every 6 hours or after model retraining).
--
-- Written by: AI Service (batch mode)
-- Read by:    .NET Backend (display to users)
CREATE TABLE [dbo].[Recommendations] (
    [RecommendationId]  BIGINT          IDENTITY(1,1) PRIMARY KEY,
    [UserId]            INT             NOT NULL REFERENCES [dbo].[Users]([UserId]),
    [ProductId]         INT             NOT NULL REFERENCES [dbo].[Products]([ProductId]),
    [Score]             FLOAT           NOT NULL,   -- Model confidence score (higher = more relevant)
    [Rank]              INT             NOT NULL,   -- 1-based position in recommendation list
    [GeneratedAt]       DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    [ModelVersion]      NVARCHAR(20)    NOT NULL DEFAULT '1.0.0',
);
GO

-- .NET reads latest recommendations per user, ordered by rank
CREATE NONCLUSTERED INDEX IX_Recommendations_User
    ON [dbo].[Recommendations] ([UserId], [GeneratedAt] DESC);
GO


-- ── 12. ModelMetadata ──────────────────────────────────────
-- Tracks AI model versions, performance metrics, and active model.
--
-- Written by: AI Service (after training)
-- Read by:    Both teams (monitoring, version display)
CREATE TABLE [dbo].[ModelMetadata] (
    [ModelId]           INT             IDENTITY(1,1) PRIMARY KEY,
    [ModelVersion]      NVARCHAR(20)    NOT NULL,   -- Semantic version e.g. '1.0.0'
    [TrainedAt]         DATETIME2       NOT NULL,
    [TestHR10]          FLOAT           NULL,       -- Test Hit Rate @ 10
    [TestNDCG10]        FLOAT           NULL,       -- Test NDCG @ 10
    [NumItems]          INT             NOT NULL,   -- Number of items in the model
    [NumUsers]          INT             NOT NULL,   -- Number of users in training data
    [CheckpointPath]    NVARCHAR(500)   NULL,       -- Path to the .pth file
    [IsActive]          BIT             NOT NULL DEFAULT 1,
);
GO


-- ════════════════════════════════════════════════════════════
-- SUMMARY
-- ════════════════════════════════════════════════════════════
-- 
-- Platform Tables (9):
--   1.  Categories       - Product categories (10 categories)
--   2.  Users            - User accounts (10,000 users)
--   3.  Products         - Product catalog (1,000 products)
--   4.  Addresses        - Shipping/billing addresses
--   5.  Orders           - Customer orders
--   6.  OrderItems       - Items within orders
--   7.  CartItems        - Shopping cart
--   8.  WishlistItems    - User wishlists
--   9.  ProductReviews   - Product reviews & ratings
--
-- AI Tables (3):
--   10. Interactions      - User behavior log (961K+ records)
--   11. Recommendations   - AI-generated recommendations
--   12. ModelMetadata     - AI model version tracking
--
-- Total: 12 tables
-- ════════════════════════════════════════════════════════════

PRINT '✅ E-Mall schema V001 applied successfully!';
PRINT '   → 12 tables created';
PRINT '   → Next step: Apply seed data from db/seeds/';
GO
