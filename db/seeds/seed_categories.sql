-- ============================================================
-- seed_categories.sql
-- E-Mall Reference Data — Categories
-- Source: categories.csv (10 rows)
-- ============================================================
--
-- This script inserts the 10 product categories used in the
-- E-Mall platform. Run AFTER V001__initial_schema.sql.
--
-- HOW TO APPLY:
--   sqlcmd -S localhost -U sa -P "YourPassword" -d EMall -i db/seeds/seed_categories.sql
-- ============================================================

USE [EMall];
GO

-- Enable IDENTITY_INSERT to preserve original category IDs
SET IDENTITY_INSERT [dbo].[Categories] ON;
GO

INSERT INTO [dbo].[Categories] ([CategoryId], [CategoryName], [Description])
VALUES
    (1,  'Electronics',                'Consumer electronics, gadgets, and tech accessories'),
    (2,  'Fashion - Men',              'Men''s clothing, shoes, and accessories'),
    (3,  'Fashion - Women',            'Women''s clothing, shoes, and accessories'),
    (4,  'Home & Kitchen',             'Home appliances, furniture, and kitchen essentials'),
    (5,  'Sports & Outdoors',          'Sports equipment, fitness gear, and outdoor essentials'),
    (6,  'Beauty & Personal Care',     'Skincare, makeup, fragrances, and grooming products'),
    (7,  'Books & Stationery',         'Books, notebooks, pens, and art supplies'),
    (8,  'Toys & Kids',               'Toys, games, educational products, and baby items'),
    (9,  'Grocery & Essentials',       'Food, beverages, cleaning, and personal hygiene'),
    (10, 'Automotive & Accessories',   'Car care, GPS, dash cams, and automotive tools');
GO

SET IDENTITY_INSERT [dbo].[Categories] OFF;
GO

PRINT '✅ 10 categories seeded successfully!';
GO
