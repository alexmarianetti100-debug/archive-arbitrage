"""
Validation Engine — circuit breaker that prevents false-positive alerts.

Catches mismatched comps by enforcing strict title matching between the
listing being evaluated and the sold comps it's being compared against.

The core problem: searching "rick owens" returns both mainline Rick Owens
and diffusion lines (DRKSHDW, Lilies) at very different price points.
A DRKSHDW cargo pant listed at $180 looks like a 60% gap when compared
against mainline comp avg of $450, but it's not a deal — it's a mismatch.

This module catches that before an alert fires.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("validation_engine")


# ── Diffusion / sub-line keywords ─────────────────────────────────────────
# If ANY of these appear in a listing title, the same keyword (or a known
# alias) MUST appear in at least one comp title — otherwise the comp set
# is pricing a different product line.

DIFFUSION_KEYWORDS: dict[str, set[str]] = {
    # Rick Owens
    "drkshdw": {"drkshdw", "dark shadow"},
    "lilies": {"lilies"},
    "hun rick owens": {"hun rick owens", "hunrickowens"},
    "champion rick": {"champion", "x champion"},
    "rick owens x adidas": {"adidas", "x adidas", "ro x adidas"},
    "rick owens x birkenstock": {"birkenstock"},
    "rick owens x converse": {"converse"},
    "rick owens x dr. martens": {"dr. martens", "dr martens"},
    "rick owens x vans": {"vans", "x vans"},
    # Comme des Garcons
    "play": {"play", "cdg play"},
    "homme plus": {"homme plus"},
    "shirt": {"cdg shirt", "comme des garcons shirt"},
    "black": {"cdg black", "comme des garcons black"},
    "junya watanabe man": {"junya watanabe man", "jw man"},
    # Yohji
    "y's": {"y's", "ys"},
    "ground y": {"ground y"},
    "s'yte": {"s'yte", "syte"},
    # Maison Margiela
    "mm6": {"mm6", "maison margiela 6"},
    "artisanal": {"artisanal"},
    # Saint Laurent
    "l'aveugle": {"l'aveugle", "laveugle", "l'aveugle par amour"},
    # Helmut Lang
    "helmut lang jeans": {"jeans"},
}

# Brands where diffusion-line detection matters most
DIFFUSION_BRANDS = {
    "rick owens", "comme des garcons", "yohji yamamoto",
    "maison margiela", "saint laurent", "helmut lang",
}


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation checks."""
    passed: bool
    reason: str
    check_name: str


class ValidationEngine:
    """Circuit breaker that validates deal quality before alerts fire.

    Usage::

        engine = ValidationEngine()
        results = engine.validate(
            listing_title="Rick Owens DRKSHDW Cargo Pants",
            comp_titles=["Rick Owens Mainline Bauhaus Cargo", ...],
            listing_size="S",
            comp_sizes=["XXL", "L", "M"],
            listing_price=180,
            comp_avg_price=450,
            query="rick owens cargo",
        )
        if not all(r.passed for r in results):
            # Block the alert
    """

    def validate(
        self,
        listing_title: str,
        comp_titles: list[str] | None = None,
        listing_size: str | None = None,
        comp_sizes: list[str] | None = None,
        listing_price: float = 0,
        comp_avg_price: float = 0,
        query: str = "",
    ) -> list[ValidationResult]:
        """Run all validation checks. Returns list of results."""
        results: list[ValidationResult] = []

        results.append(self.check_diffusion_match(listing_title, comp_titles or [], query))
        results.append(self.check_size_parity(listing_size, comp_sizes or [], listing_price, comp_avg_price))

        return results

    # ── Check 1: Diffusion / sub-line mismatch ───────────────────────────

    def check_diffusion_match(
        self,
        listing_title: str,
        comp_titles: list[str],
        query: str = "",
    ) -> ValidationResult:
        """Ensure diffusion-line keywords in the listing also appear in comps.

        If the listing says "DRKSHDW" but none of the comps mention it, the
        comps are pricing mainline Rick Owens — completely different product.
        """
        title_lower = listing_title.lower()

        # Find which diffusion keywords appear in the listing title
        listing_diffusion_hits: list[str] = []
        for keyword, aliases in DIFFUSION_KEYWORDS.items():
            if any(a in title_lower for a in aliases) or keyword in title_lower:
                listing_diffusion_hits.append(keyword)

        if not listing_diffusion_hits:
            return ValidationResult(
                passed=True,
                reason="no diffusion keywords in listing",
                check_name="diffusion_match",
            )

        if not comp_titles:
            # No comp titles available — can't verify, pass with warning
            return ValidationResult(
                passed=True,
                reason="no comp titles to check against",
                check_name="diffusion_match",
            )

        # Check if at least one comp title contains the same diffusion keyword
        comp_text = " ".join(t.lower() for t in comp_titles)
        for keyword in listing_diffusion_hits:
            aliases = DIFFUSION_KEYWORDS[keyword]
            if any(a in comp_text for a in aliases) or keyword in comp_text:
                continue  # This keyword is represented in comps
            # Mismatch found
            logger.info(
                f"Diffusion mismatch: listing has '{keyword}' but no comps match. "
                f"Listing: {listing_title[:60]}"
            )
            return ValidationResult(
                passed=False,
                reason=f"diffusion keyword '{keyword}' in listing but not in any comp",
                check_name="diffusion_match",
            )

        return ValidationResult(
            passed=True,
            reason="diffusion keywords matched in comps",
            check_name="diffusion_match",
        )

    # ── Check 2: Size parity ─────────────────────────────────────────────

    _LETTER_SIZES = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
    _SIZE_RE = re.compile(r"\b(XXS|XS|XXXL|XXL|XL|S|M|L)\b", re.IGNORECASE)

    def check_size_parity(
        self,
        listing_size: str | None,
        comp_sizes: list[str],
        listing_price: float = 0,
        comp_avg_price: float = 0,
    ) -> ValidationResult:
        """Reject when listing size is far from comp sizes and price variance > 20%.

        A Size S listing compared against Size XXL comps is unreliable if
        the price difference between those sizes exceeds 20%.
        """
        if not listing_size or not comp_sizes:
            return ValidationResult(
                passed=True,
                reason="size data unavailable",
                check_name="size_parity",
            )

        listing_idx = self._size_index(listing_size)
        if listing_idx is None:
            return ValidationResult(
                passed=True,
                reason="listing size not parseable",
                check_name="size_parity",
            )

        comp_indices = [self._size_index(s) for s in comp_sizes]
        comp_indices = [i for i in comp_indices if i is not None]
        if not comp_indices:
            return ValidationResult(
                passed=True,
                reason="comp sizes not parseable",
                check_name="size_parity",
            )

        # Check if any comp is 3+ size steps away (e.g., S vs XXL)
        max_distance = max(abs(listing_idx - ci) for ci in comp_indices)
        median_comp_idx = sorted(comp_indices)[len(comp_indices) // 2]
        median_distance = abs(listing_idx - median_comp_idx)

        if median_distance < 3:
            return ValidationResult(
                passed=True,
                reason=f"size distance {median_distance} within tolerance",
                check_name="size_parity",
            )

        # Distance >= 3 — check if price variance is > 20%
        if listing_price > 0 and comp_avg_price > 0:
            variance = abs(comp_avg_price - listing_price) / comp_avg_price
            if variance > 0.20:
                logger.info(
                    f"Size parity fail: listing={listing_size} vs median comp "
                    f"size index={median_comp_idx}, price variance={variance:.0%}"
                )
                return ValidationResult(
                    passed=False,
                    reason=(
                        f"size mismatch ({listing_size} vs comps) with "
                        f"{variance:.0%} price variance (>20%)"
                    ),
                    check_name="size_parity",
                )

        return ValidationResult(
            passed=True,
            reason="size distance large but price variance acceptable",
            check_name="size_parity",
        )

    def _size_index(self, size_str: str) -> int | None:
        """Map a size string to an ordinal index."""
        if not size_str:
            return None
        m = self._SIZE_RE.search(size_str.upper())
        if m:
            try:
                return self._LETTER_SIZES.index(m.group(1).upper())
            except ValueError:
                return None
        return None
