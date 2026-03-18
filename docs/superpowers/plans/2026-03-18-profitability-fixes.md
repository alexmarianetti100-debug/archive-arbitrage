# Profitability Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan.

**Goal:** Fix the 3 highest-impact profitability issues: execution tracking, platform-specific fees, and comp quality floor.

**Architecture:** Surgical changes to existing functions. No new files needed.

**Tech Stack:** Python, SQLite, JSONL

---

### Task 1: Fix comp quality floor (0.5 → proportional)

**Files:** `scrapers/comp_matcher.py:23-30`

Change quality_weight so bad comps (quality_score=0.0) get 0x weight instead of 0.5x.

### Task 2: Platform-specific fee model

**Files:** `gap_hunter.py:1940-1946`

Replace hardcoded `0.858` with a platform fee lookup. Default to Grailed fees but make it data-driven.

### Task 3: Execution tracking — add missing fields

**Files:** `core/deal_tracker.py:25-46`, `gap_hunter.py:2573-2584`

Add `buy_price`, `actual_profit`, `deal_status`, `sell_platform` fields to DealPrediction so deals can be tracked end-to-end.
