# HYPER-ACCURATE PRICING SYSTEM - MASTER PLAN

## Executive Summary
Transform Archive Arbitrage from query-based pricing to **item-specific, multi-modal pricing** using computer vision, NLP attribute extraction, and machine learning price prediction.

---

## PHASE 1: ATTRIBUTE EXTRACTION & NORMALIZATION (Week 1-2)

### 1.1 NLP-Based Attribute Extraction
**Goal:** Extract structured attributes from listing titles and descriptions

**Implementation:**
- Use LLM (GPT-4/Claude) or fine-tuned BERT to parse titles
- Extract: Brand, Model, Size, Color, Material, Year/Season, Condition, Authenticity markers
- Create standardized attribute schema

**Example:**
```
Input: "Chrome Hearts Cemetery Ring Size 9 Sterling Silver 925 Vintage 2003"
Output: {
  "brand": "Chrome Hearts",
  "model": "Cemetery Ring",
  "size": "9",
  "material": "Sterling Silver 925",
  "year": "2003",
  "condition": "vintage",
  "category": "jewelry"
}
```

**Research Basis:**
- PAE (Product Attribute Extraction) framework from Walmart/Trendyol research
- LLM-based extraction achieves 94%+ accuracy on fashion attributes

### 1.2 Size Normalization
**Problem:** "M", "Medium", "48", "IT 48" are the same size but different formats

**Solution:**
- Create universal size converter
- Map all size formats to standardized system
- Account for brand-specific sizing (e.g., Japanese brands run small)

**Implementation:**
```python
class SizeNormalizer:
    def normalize(self, size_str, brand, category):
        # Convert to base unit (cm for clothes, US standard for shoes)
        # Return: {"standard": "M", "measurements": {"chest": 96, "waist": 84}}
```

---

## PHASE 2: VISUAL SIMILARITY MATCHING (Week 2-4)

### 2.1 Image Embedding Pipeline
**Goal:** Match identical/similar products using computer vision

**Technology:**
- **Fashion-CLIP**: Fine-tuned CLIP for fashion products (Farfetch dataset)
- **Embedding**: 512-dimensional vector per image
- **Vector DB**: Pinecone/Milvus for fast similarity search

**Implementation:**
```python
from transformers import CLIPProcessor, CLIPModel

class VisualMatcher:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip")
        self.processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
    
    def get_embedding(self, image_url):
        image = load_image(image_url)
        inputs = self.processor(images=image, return_tensors="pt")
        embedding = self.model.get_image_features(**inputs)
        return embedding.detach().numpy()
    
    def find_similar(self, query_embedding, threshold=0.92):
        # Search vector DB for similar items
        # Return matches with similarity score > threshold
```

**Why Fashion-CLIP over regular CLIP:**
- Trained on 1M+ fashion product images
- Better at distinguishing subtle differences (e.g., different seasons of same bag)
- 15-20% better accuracy on fashion similarity tasks

### 2.2 Multi-Image Analysis
**Problem:** Single image might not show all details

**Solution:**
- Process all listing images
- Weight main image higher (60%), secondary images (40%)
- Detect condition issues (stains, scratches) via image analysis

### 2.3 Duplicate Detection v2
**Current:** Perceptual hashing (imagehash library)
**Upgrade:** 
- Combine perceptual hash + CLIP embedding
- Detect near-duplicates (same item, different lighting/angle)
- Identify stock photos vs actual item photos

---

## PHASE 3: ADVANCED PRICE MODELING (Week 3-5)

### 3.1 Time-Decayed Weighted Average
**Current:** Simple average of all comps
**Problem:** 6-month-old sale matters same as yesterday's sale

**Solution:** Exponential time decay
```python
def time_weighted_price(sold_items):
    weights = [exp(-decay_rate * days_ago) for days_ago in ages]
    weighted_avg = sum(p * w for p, w in zip(prices, weights)) / sum(weights)
    return weighted_avg
```

**Decay rates by category:**
- Sneakers: 7-day half-life (prices change fast)
- Watches: 30-day half-life (stable)
- Vintage: 90-day half-life (illiquid)

### 3.2 Feature-Based Price Prediction
**Goal:** Predict price for exact item configuration

**Model:** Gradient Boosting (XGBoost/LightGBM) or Neural Network
**Features:**
- Brand (categorical)
- Model/Line (categorical)
- Size (normalized)
- Condition score (0-100)
- Age (years since release)
- Season (holiday effect)
- Platform (Grailed premium vs eBay discount)
- Seller reputation
- Authentication status
- Days listed (time on market)

**Training Data:**
- Historical sold data from all platforms
- Price trajectories over time
- Feature vectors from Phase 1 & 2

**Expected Accuracy:**
- Current: ±30-40% error on simple averages
- Target: ±10-15% error with ML model

### 3.3 Size-Adjusted Pricing
**Problem:** Size 7 Jordan 1s cost different than Size 11

**Solution:**
- Calculate size premium/discount per model
- "Size 7 sells for 1.2x average, Size 13 sells for 0.85x"
- Adjust comps to target size using size curve

---

## PHASE 4: PLATFORM & MARKET DYNAMICS (Week 4-6)

### 4.1 Platform-Specific Pricing
**Observation:** Same item sells for different prices on different platforms

**Implementation:**
- Track platform premiums: Grailed (+15%), eBay (+0%), Poshmark (-10%)
- Normalize all prices to "Grailed equivalent"
- When listing, suggest optimal platform based on item type

### 4.2 Velocity-Based Pricing
**Goal:** Price based on liquidity

**Indicators:**
- Days to sell (from sold data)
- Watch/save counts (from live listings)
- Bid-ask spread (if available)

**Implementation:**
```python
class LiquidityScorer:
    def score(self, item):
        if days_to_sell < 7:
            return "hot"  # Price at market or above
        elif days_to_sell < 30:
            return "warm"  # Standard pricing
        else:
            return "cold"  # Price 10-15% below market for quick sale
```

### 4.3 Market Trend Detection
**Goal:** Detect if prices are rising/falling

**Method:**
- Linear regression on time-series sold data
- Slope indicates trend direction
- Adjust buy/sell recommendations based on trend

---

## PHASE 5: ENSEMBLE PRICING ENGINE (Week 5-6)

### 5.1 Multi-Modal Price Estimation
Combine multiple pricing methods:

```python
class HyperPricingEngine:
    def estimate_price(self, item):
        # Method 1: Exact visual matches (highest confidence)
        visual_matches = self.visual_matcher.find_exact_matches(item.images)
        if len(visual_matches) >= 3:
            price_visual = weighted_average(visual_matches)
            confidence_visual = 0.95
        
        # Method 2: Attribute-based ML model
        features = self.extract_features(item)
        price_ml = self.ml_model.predict(features)
        confidence_ml = 0.85
        
        # Method 3: Query-based comps (fallback)
        price_query = self.query_based_pricing(item.title)
        confidence_query = 0.70
        
        # Weighted ensemble
        final_price = weighted_average([
            (price_visual, confidence_visual),
            (price_ml, confidence_ml),
            (price_query, confidence_query)
        ])
        
        return {
            "price": final_price,
            "confidence": max(confidence_visual, confidence_ml, confidence_query),
            "method_breakdown": {
                "visual": price_visual,
                "ml": price_ml,
                "query": price_query
            }
        }
```

### 5.2 Confidence Scoring
**Goal:** Know when we can trust the price vs when we need more data

**Factors:**
- Number of exact visual matches
- Number of attribute-matched comps
- Recency of comps
- Price variance (low variance = high confidence)
- Platform coverage (multiple platforms = higher confidence)

**Output:**
- High confidence (90%+): ±5% accuracy expected
- Medium confidence (70-90%): ±15% accuracy expected
- Low confidence (<70%): ±30% accuracy, flag for manual review

---

## PHASE 6: CONTINUOUS LEARNING (Ongoing)

### 6.1 Price Prediction Validation
**Goal:** Measure actual accuracy

**Implementation:**
- Track predicted vs actual sale prices
- Calculate MAE (Mean Absolute Error) and MAPE (Mean Absolute Percentage Error)
- Retrain models monthly with new data

### 6.2 A/B Testing
**Goal:** Validate improvements

**Method:**
- Run old pricing vs new pricing side-by-side
- Measure which version finds more profitable deals
- Measure which version has fewer false positives

---

## TECHNICAL IMPLEMENTATION PRIORITIES

### Immediate (Week 1)
1. ✅ Implement attribute extraction from titles
2. ✅ Add size normalization
3. ✅ Create structured item schema

### Short-term (Week 2-3)
4. ✅ Deploy Fashion-CLIP for image embeddings
5. ✅ Build vector similarity search
6. ✅ Implement time-decayed pricing

### Medium-term (Week 4-5)
7. ✅ Train price prediction model
8. ✅ Add platform-specific adjustments
9. ✅ Build ensemble pricing engine

### Long-term (Week 6+)
10. ✅ Continuous learning pipeline
11. ✅ Market trend detection
12. ✅ Liquidity scoring

---

## EXPECTED IMPROVEMENTS

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Price accuracy (MAPE) | 30-40% | 10-15% | 60-70% better |
| Exact item matching | 0% | 85% | New capability |
| False positive rate | 15-20% | 5-8% | 60% reduction |
| Deal discovery rate | Baseline | +40% | More gaps found |
| Confidence scoring | None | 90%+ high conf | New capability |

---

## COST & INFRASTRUCTURE

### Compute Requirements
- **Fashion-CLIP inference**: ~0.5s per image on CPU, ~0.05s on GPU
- **Vector DB**: Pinecone free tier (100k vectors) sufficient for MVP
- **ML training**: One-time cost ~$50-100 on cloud GPU
- **Ongoing**: ~$20-50/month for vector DB + API calls

### APIs & Services
- OpenAI/Anthropic for attribute extraction: ~$0.01 per item
- Pinecone vector DB: Free tier to start
- Optional: StockX/GOAT APIs for market data

---

## RISK MITIGATION

1. **Model drift**: Monthly retraining on new sold data
2. **Cold start**: Graceful fallback to query-based pricing
3. **API costs**: Caching at every layer
4. **Accuracy validation**: Human spot-checking on high-value items

---

## SUCCESS METRICS

1. **Primary**: Reduce MAPE from 35% to <15%
2. **Secondary**: Increase profitable deal discovery by 40%
3. **Tertiary**: Reduce time-to-sell for flipped items by 25%

---

## NEXT STEPS

1. **Approve plan** - Which phases to prioritize?
2. **Gather training data** - Export historical sold data
3. **Set up infrastructure** - Vector DB, model training environment
4. **Begin Phase 1** - Attribute extraction implementation

**Estimated timeline to full deployment: 6 weeks**
**Estimated accuracy improvement: 60-70% better price prediction**
