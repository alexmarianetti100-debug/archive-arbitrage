---
name: Deal Quality Research March 2026
description: Comprehensive research on sold comp accuracy, platform fees, replica detection, condition grading, seller trust, and shipping costs — with actionable recommendations
type: reference
---

## Grailed Sold Price Accuracy
- Grailed `sold_price` field = ACTUAL transaction price (accepted offer), NOT listing price. Confirmed via multiple sources and Algolia API field analysis.
- eBay "Best Offer Accepted" listings show ORIGINAL listing price, not accepted offer. Need 10-15% haircut on eBay comps with Best Offer.
- Grailed offer minimum is 60% of listing. Sellers list 15-20% above target to leave negotiation room.

## Platform Fee Rates (March 2026)
- Grailed: 9% commission + 3.49%+$0.49 Stripe = ~12.5% domestic, 14-16% international
- eBay clothing: 13.6% (no store) / 12.7% (store) + $0.40 per-order
- eBay sneakers >= $150: 8% (no store) / 7% (store), no per-order fee
- eBay jewelry/watches <= $5K: 15%
- Poshmark: $2.95 flat (under $15) or 20% (over $15)
- TRR: 20-85% commission (80% take for clothing $0-$99, 70% for bags $1.5K-$5K)
- Fashionphile: 30% consignment fee (15% for items $3K+)
- Current system uses 14.2% (0.858x) for Grailed — slightly conservative but good safety margin

## Chrome Hearts Authentication
- Weight is #1 tell: fakes ~5g lighter on pendants
- RN# 95024 on clothing tags: fakes print it faint/low-res
- "Made in USA" required for all authentic CH clothing
- CH does not sell online — every resale piece was in-store purchase
- Category-specific price floors needed: jewelry $250, clothing $250, eyewear $300

## Seller Trust Thresholds
- Grailed Trusted Seller badge: 20+ sales, 4.9+ rating
- Current system min 3 sales — too low for high-value items
- Recommended: 5 sales for $500+ items, 10 sales for $1,000+ items, 10 for any CH jewelry

## Shipping Costs 2026
- USPS average increase 7.8%, UPS/FedEx 5.9% base (7-12% effective with surcharges)
- Japan cross-border (2nd STREET): $35-$55 depending on weight
- 20% buffer on estimates is good practice, keep it

## Condition Grading Industry Standard
- Pristine/NWT: 95-100% of market (our 1.00x correct)
- Excellent: 85-94% (our 0.90x correct)
- Very Good: 70-84% (our 0.70x slightly low, recommend 0.75x)
- Good: 50-69% (our 0.50x slightly low, recommend 0.55x)
- Fair: 30-49% (our 0.30x slightly low, recommend 0.35x)
- Packaging adds 15% (box, receipt, dust bag, auth card)
- Conservative default for unstated condition (0.50x) is correct and important

## Market Trends March 2026
- Raf Simons pre-2005: extreme appreciation (Riot bomber $47K documented)
- Rick Owens archive: strong demand, FW06 Dustulator pieces most sought
- Balenciaga post-Demna: uncertainty, shorten comp window to 60 days
- Gallery Dept: oversaturation compressing margins, require more comps
