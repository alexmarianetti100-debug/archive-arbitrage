-- Comp Pipeline Diagnostic Queries
-- Run after a cycle: sqlite3 data/archive.db < scripts/comp_diagnostic.sql

-- 1. New items (last 24h) — comp count and quality
SELECT '=== NEW ITEMS (last 24h) ===';
SELECT
    COUNT(*) as new_items,
    ROUND(AVG(comp_count), 1) as avg_comps,
    SUM(CASE WHEN comp_count >= 10 THEN 1 ELSE 0 END) as with_10_comps,
    SUM(CASE WHEN comp_count < 5 THEN 1 ELSE 0 END) as under_5_comps
FROM items
WHERE status = 'active'
  AND created_at > datetime('now', '-1 day');

-- 2. Score quality on new items' comps (should be 100% real, 0% synthetic)
SELECT '';
SELECT '=== COMP SCORE QUALITY (new items) ===';
SELECT
    COUNT(*) as total_comps,
    SUM(CASE WHEN similarity_score IN (0.97, 0.94, 0.91, 0.88, 0.85, 0.82, 0.79, 0.76, 0.73, 0.70, 0.67, 0.64, 0.61, 0.58, 0.55) THEN 1 ELSE 0 END) as synthetic,
    COUNT(*) - SUM(CASE WHEN similarity_score IN (0.97, 0.94, 0.91, 0.88, 0.85, 0.82, 0.79, 0.76, 0.73, 0.70, 0.67, 0.64, 0.61, 0.58, 0.55) THEN 1 ELSE 0 END) as real_scores,
    ROUND(AVG(similarity_score), 3) as avg_sim
FROM item_comps ic
JOIN items i ON i.id = ic.item_id
WHERE i.created_at > datetime('now', '-1 day');

-- 3. Image data on recently fetched comps
SELECT '';
SELECT '=== IMAGE DATA (new sold_comps) ===';
SELECT
    COUNT(*) as total_sold_comps,
    SUM(CASE WHEN image_url IS NOT NULL AND image_url != '' THEN 1 ELSE 0 END) as has_image_url,
    SUM(CASE WHEN phash IS NOT NULL AND phash != '' THEN 1 ELSE 0 END) as has_phash
FROM sold_comps
WHERE fetched_at > datetime('now', '-1 day');

-- 4. Overall system health
SELECT '';
SELECT '=== OVERALL SYSTEM HEALTH ===';
SELECT
    (SELECT COUNT(*) FROM items WHERE status = 'active') as active_items,
    (SELECT COUNT(*) FROM sold_comps) as total_sold_comps,
    (SELECT COUNT(*) FROM sold_comps WHERE image_url IS NOT NULL AND image_url != '') as comps_with_image,
    (SELECT COUNT(*) FROM sold_comps WHERE phash IS NOT NULL AND phash != '') as comps_with_phash,
    (SELECT COUNT(*) FROM comp_pair_rejections WHERE times_rejected > 0) as pair_rejections;

-- 5. Top rejection pairs (parser blind spots)
SELECT '';
SELECT '=== TOP REJECTION PAIRS (parser blind spots) ===';
SELECT
    sc.title AS comp_title,
    cpr.context_model,
    cpr.times_rejected,
    cpr.times_matched,
    ROUND(MAX(0.2, 1.0 - (CAST(cpr.times_rejected AS REAL) / MAX(cpr.times_matched, 1))), 2) AS pair_quality
FROM comp_pair_rejections cpr
JOIN sold_comps sc ON sc.id = cpr.sold_comp_id
WHERE cpr.times_rejected > 0
ORDER BY cpr.times_rejected DESC
LIMIT 10;
