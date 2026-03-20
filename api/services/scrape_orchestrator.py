"""
Scrape orchestration service — wraps existing scrapers with progress events
for the control panel frontend via SSE.
"""

import asyncio
import time
import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger("scrape_orchestrator")


class ScrapeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScrapeEvent:
    type: str
    timestamp: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self):
        return {"type": self.type, "timestamp": self.timestamp, "data": self.data}


@dataclass
class ScrapeRun:
    run_id: str
    status: ScrapeStatus
    mode: str  # "gap_hunter" | "full_scrape"
    config: Dict[str, Any]
    started_at: str
    completed_at: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    events: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    def to_summary(self):
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "mode": self.mode,
            "config": self.config,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stats": self.stats,
            "error": self.error,
        }


# In-memory store for active/recent runs
_runs: Dict[str, ScrapeRun] = {}
MAX_HISTORY = 20


def get_run(run_id: str) -> Optional[ScrapeRun]:
    return _runs.get(run_id)


def get_active_run() -> Optional[ScrapeRun]:
    for run in _runs.values():
        if run.status == ScrapeStatus.RUNNING:
            return run
    return None


def get_run_history() -> List[Dict]:
    runs = sorted(_runs.values(), key=lambda r: r.started_at, reverse=True)
    return [r.to_summary() for r in runs[:MAX_HISTORY]]


async def cancel_run(run_id: str) -> bool:
    run = _runs.get(run_id)
    if not run or run.status != ScrapeStatus.RUNNING:
        return False
    if run._task and not run._task.done():
        run._task.cancel()
    run.status = ScrapeStatus.CANCELLED
    run.completed_at = datetime.utcnow().isoformat()
    await run.events.put(ScrapeEvent(type="scrape:cancelled", data={"run_id": run_id}))
    return True


async def start_scrape(
    mode: str,
    platforms: Optional[List[str]] = None,
    query_source: str = "trend_engine",
    custom_queries: Optional[List[str]] = None,
    max_results_per_query: int = 15,
    min_margin: float = 0.25,
    min_profit: float = 50,
    skip_auth: bool = False,
    dry_run: bool = False,
    skip_japan: bool = False,
    max_targets: Optional[int] = None,
) -> ScrapeRun:
    """Start a scrape run in the background."""
    # Only one scrape at a time
    active = get_active_run()
    if active:
        raise RuntimeError(f"Scrape already running: {active.run_id}")

    run_id = str(uuid.uuid4())[:8]
    config = {
        "mode": mode,
        "platforms": platforms,
        "query_source": query_source,
        "custom_queries": custom_queries,
        "max_results_per_query": max_results_per_query,
        "min_margin": min_margin,
        "min_profit": min_profit,
        "skip_auth": skip_auth,
        "dry_run": dry_run,
        "skip_japan": skip_japan,
        "max_targets": max_targets,
    }

    run = ScrapeRun(
        run_id=run_id,
        status=ScrapeStatus.RUNNING,
        mode=mode,
        config=config,
        started_at=datetime.utcnow().isoformat(),
    )
    _runs[run_id] = run

    # Trim old history
    if len(_runs) > MAX_HISTORY:
        oldest_key = min(
            (k for k, v in _runs.items() if v.status != ScrapeStatus.RUNNING),
            key=lambda k: _runs[k].started_at,
            default=None,
        )
        if oldest_key:
            del _runs[oldest_key]

    # Start the scrape in a background task
    if mode == "gap_hunter":
        run._task = asyncio.create_task(_run_gap_hunter(run))
    elif mode == "full_scrape":
        run._task = asyncio.create_task(_run_full_scrape(run))
    else:
        run.status = ScrapeStatus.FAILED
        run.error = f"Unknown mode: {mode}"
        run.completed_at = datetime.utcnow().isoformat()

    return run


async def _emit(run: ScrapeRun, event_type: str, data: Dict[str, Any] = None):
    """Push an event to the run's SSE queue."""
    event = ScrapeEvent(type=event_type, data=data or {})
    await run.events.put(event)


async def _run_gap_hunter(run: ScrapeRun):
    """Execute a gap hunter cycle and emit progress events."""
    try:
        await _emit(run, "scrape:started", {
            "run_id": run.run_id,
            "mode": "gap_hunter",
            "config": run.config,
        })

        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from gap_hunter import GapHunter

        hunter = GapHunter()
        config = run.config

        # Determine query options
        custom_queries = config.get("custom_queries")
        max_targets = config.get("max_targets")
        skip_japan = config.get("skip_japan", False)

        await _emit(run, "scrape:progress", {
            "phase": "initializing",
            "message": "Gap Hunter initialized, starting cycle...",
        })

        # Override the hunter's process_deal to capture deals
        original_process_deal = hunter.process_deal
        deals_found = []

        async def instrumented_process_deal(item, **kwargs):
            result = await original_process_deal(item, **kwargs)
            if result:
                deals_found.append({
                    "title": getattr(item, "title", "")[:80],
                    "brand": getattr(item, "brand", ""),
                    "price": getattr(item, "source_price", 0),
                    "source": getattr(item, "source", ""),
                })
                await _emit(run, "scrape:deal_found", {
                    "deal_number": len(deals_found),
                    "title": getattr(item, "title", "")[:80],
                    "brand": getattr(item, "brand", ""),
                    "price": getattr(item, "source_price", 0),
                    "source": getattr(item, "source", ""),
                })
            return result

        hunter.process_deal = instrumented_process_deal

        await _emit(run, "scrape:progress", {
            "phase": "scanning",
            "message": "Running gap hunt cycle...",
        })

        await hunter.run_cycle(
            custom_queries=custom_queries,
            max_targets=max_targets,
            skip_japan=skip_japan,
        )

        # Collect stats
        run.stats = {
            "deals_found": len(deals_found),
            "deals_sent": hunter.stats.get("deals_sent", 0),
            "auth_blocked": hunter.stats.get("auth_blocked", 0),
            "quality_filtered": hunter.stats.get("quality_filtered", 0),
            "seen_ids": len(hunter.seen_ids),
            "cycle": hunter.cycle_count,
        }

        run.status = ScrapeStatus.COMPLETED
        run.completed_at = datetime.utcnow().isoformat()

        await _emit(run, "scrape:complete", {
            "run_id": run.run_id,
            "stats": run.stats,
            "duration_seconds": round(
                (datetime.fromisoformat(run.completed_at) - datetime.fromisoformat(run.started_at)).total_seconds()
            ),
        })

    except asyncio.CancelledError:
        run.status = ScrapeStatus.CANCELLED
        run.completed_at = datetime.utcnow().isoformat()
        await _emit(run, "scrape:cancelled", {"run_id": run.run_id})
    except Exception as e:
        logger.exception(f"Gap hunter run {run.run_id} failed")
        run.status = ScrapeStatus.FAILED
        run.error = str(e)
        run.completed_at = datetime.utcnow().isoformat()
        await _emit(run, "scrape:error", {"run_id": run.run_id, "error": str(e)})


async def _run_full_scrape(run: ScrapeRun):
    """Execute a full scrape and emit progress events."""
    try:
        await _emit(run, "scrape:started", {
            "run_id": run.run_id,
            "mode": "full_scrape",
            "config": run.config,
        })

        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from scrapers.full_scrape import run_full_scrape

        config = run.config

        await _emit(run, "scrape:progress", {
            "phase": "running",
            "message": "Starting full platform scrape...",
        })

        await run_full_scrape(
            num_queries=config.get("max_targets") or 20,
            max_per_source=config.get("max_results_per_query", 15),
            min_margin=config.get("min_margin", 0.25),
            min_profit=config.get("min_profit", 50),
            skip_auth=config.get("skip_auth", False),
            dry_run=config.get("dry_run", False),
            fresh=True,
        )

        run.status = ScrapeStatus.COMPLETED
        run.completed_at = datetime.utcnow().isoformat()

        await _emit(run, "scrape:complete", {
            "run_id": run.run_id,
            "stats": run.stats,
            "duration_seconds": round(
                (datetime.fromisoformat(run.completed_at) - datetime.fromisoformat(run.started_at)).total_seconds()
            ),
        })

    except asyncio.CancelledError:
        run.status = ScrapeStatus.CANCELLED
        run.completed_at = datetime.utcnow().isoformat()
        await _emit(run, "scrape:cancelled", {"run_id": run.run_id})
    except Exception as e:
        logger.exception(f"Full scrape run {run.run_id} failed")
        run.status = ScrapeStatus.FAILED
        run.error = str(e)
        run.completed_at = datetime.utcnow().isoformat()
        await _emit(run, "scrape:error", {"run_id": run.run_id, "error": str(e)})
