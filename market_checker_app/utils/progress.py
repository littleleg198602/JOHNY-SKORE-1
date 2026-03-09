from __future__ import annotations

import logging
import time


def log_heartbeat(logger: logging.Logger, phase: str, i: int, n: int, t0: float) -> None:
    elapsed = max(0.0, time.time() - t0)
    avg = (elapsed / i) if i else 0.0
    eta = max(0.0, (n - i) * avg)
    logger.info("%s %s/%s (%.1f%%) elapsed=%.1fs eta=%.1fs", phase, i, n, (i / n * 100.0) if n else 100.0, elapsed, eta)
