-- Database Initialization Script for EcoBuild

-- Drop tables if they exist (For clean rebuilding during testing)
DROP TABLE IF EXISTS "scraped_price" CASCADE;
DROP TABLE IF EXISTS "component" CASCADE;
DROP TABLE IF EXISTS "psu" CASCADE;
DROP TABLE IF EXISTS "storage" CASCADE;
DROP TABLE IF EXISTS "ram" CASCADE;
DROP TABLE IF EXISTS "case" CASCADE;
DROP TABLE IF EXISTS "cooler" CASCADE;
DROP TABLE IF EXISTS "motherboard" CASCADE;
DROP TABLE IF EXISTS "gpu" CASCADE;
DROP TABLE IF EXISTS "cpu" CASCADE;

-- 1. CPU Table
CREATE TABLE "cpu" (
    "cpu_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "socket" VARCHAR(20) NOT NULL,
    "tdp_watts" INTEGER NOT NULL,
    "base_score" INTEGER NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 2. Motherboard Table
CREATE TABLE "motherboard" (
    "mobo_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "socket" VARCHAR(20) NOT NULL,
    "form_factor" VARCHAR(20) NOT NULL,
    "ram_type" VARCHAR(10) NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 3. GPU Table
CREATE TABLE "gpu" (
    "gpu_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "pcie_slot" VARCHAR(20) NOT NULL,
    "tdp_watts" INTEGER NOT NULL,
    "base_score" INTEGER NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 4. Cooler Table
CREATE TABLE "cooler" (
    "cooler_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "socket_list" TEXT NOT NULL,
    "max_tdp" INTEGER NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 5. Case Table
CREATE TABLE "case" (
    "case_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "form_factor" VARCHAR(20) NOT NULL,
    "airflow_coef" NUMERIC(3,2) NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 6. RAM Table
CREATE TABLE "ram" (
    "ram_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "ram_type" VARCHAR(10) NOT NULL,
    "capacity_gb" INTEGER NOT NULL,
    "speed_mhz" INTEGER NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 7. Storage Table
CREATE TABLE "storage" (
    "storage_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "type" VARCHAR(20) NOT NULL,
    "capacity_gb" INTEGER NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 8. Power Supply Table (PSU)
CREATE TABLE "psu" (
    "psu_id" VARCHAR(50) PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "wattage" INTEGER NOT NULL,
    "efficiency" VARCHAR(20) NOT NULL,
    "price" NUMERIC(7,2) NOT NULL
);

-- 9. General Component Mapping Registry
CREATE TABLE "component" (
    "component_id" VARCHAR(50) PRIMARY KEY,
    "model_key" VARCHAR(50) NOT NULL,
    "type" VARCHAR(20) NOT NULL
);

-- 10. Scraped Price Table
CREATE TABLE "scraped_price" (
    "price_id" SERIAL PRIMARY KEY,
    "model_key" VARCHAR(50) NOT NULL,
    "platform" VARCHAR(20) NOT NULL,
    "price_rm" NUMERIC(7,2) NOT NULL,
    "shipping_rm" NUMERIC(5,2) NOT NULL
);