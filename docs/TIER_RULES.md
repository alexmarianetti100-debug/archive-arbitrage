# Discord Tier Rules

The Discord routing policy is configured in:

```text
config/tier_rules.json
```

This file controls which deals qualify for Beginner, Pro, and Big Baller channels.

## Top-level structure

```json
{
  "beginner": { ... },
  "pro": { ... },
  "big_baller": { ... },
  "strict_auth_brands": [ ... ],
  "terms": { ... }
}
```

---

## Tier blocks

Each tier block can contain:

- `min_profit` — minimum dollar profit required
- `min_margin` — minimum margin required (decimal, e.g. `0.30` = 30%)
- `min_liquidity` — minimum liquidity score required
- `max_price` — maximum item price allowed for the tier (optional)
- `min_price` — minimum item price allowed for the tier (optional)
- `min_auth` — minimum auth confidence required (optional)
- `strict_auth_min` — higher auth threshold for strict-auth categories (optional)
- `brands` — allowed brands for this tier
- `routing` — which Discord channels receive deals qualifying for this tier

### Example

```json
"beginner": {
  "min_profit": 150,
  "min_margin": 0.30,
  "min_liquidity": 8.0,
  "max_price": 2500,
  "brands": ["chrome hearts", "prada", "rick owens"],
  "routing": ["beginner", "pro", "big_baller"]
}
```

---

## strict_auth_brands

Brands listed in `strict_auth_brands` require a higher auth threshold when classified for Pro / Big Baller.

Use this for categories where counterfeit risk is high or mistakes are expensive.

Examples:
- Rolex
- Cartier
- Hermès
- Chanel
- Patek Philippe

---

## terms

The `terms` section helps the classifier infer broad item types from titles.

Supported groups:
- `watch`
- `bag`
- `jewelry`
- `shoe`
- `archive`

These are simple keyword lists used by the policy module.

If the classifier is missing obvious matches, update these lists.

---

## Routing model

The current model uses nested entitlement routing:

- Beginner-worthy deal → `beginner`, `pro`, `big_baller`
- Pro-worthy deal → `pro`, `big_baller`
- Big Baller-worthy deal → `big_baller`

That behavior is controlled by each tier's `routing` array.

---

## Validation

Before relying on edits, run:

```bash
source venv/bin/activate
python scripts/verify/validate_tier_rules.py
```

This checks:
- JSON can be parsed
- expected top-level keys exist
- required per-tier fields exist
- brands are lists
- routing values are valid tier names
- thresholds are numeric
- sample classifications still work

---

## Editing guidance

When changing rules:

1. change one thing at a time
2. run the validator
3. run a bounded smoke test:

```bash
source venv/bin/activate
python gap_hunter.py --once --max-targets 1 --skip-japan
```

4. watch logs for tier decisions

---

## Good tuning examples

### Tighten Beginner risk
- raise `min_liquidity`
- lower `max_price`
- remove riskier brands from Beginner `brands`

### Make Pro stricter on luxury
- raise `min_auth`
- raise `strict_auth_min`
- expand `strict_auth_brands`

### Expand Big Baller coverage
- add new grail brands to `big_baller.brands`
- add title keywords to `terms.archive`, `terms.watch`, or `terms.bag`

---

## Reminder

This config affects Discord tier routing, not the full hunt logic.
The deal still has to survive Gap Hunter's pricing, auth, and public-send gates first.
