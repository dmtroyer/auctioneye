"""AWS Lambda entry point for the auction watcher.

Deployed with handler string ``src.lambda_handler.handler``. Invoked on a
schedule by EventBridge Scheduler; ignores the event payload and runs a single
watcher pass, returning the run summary.
"""
import logging

from .config import Config
from .watcher import create_watcher, setup_logging


def handler(event, context):
    """Run a single auction watcher pass.

    Args:
        event: Event payload (unused).
        context: Lambda context (unused).

    Returns:
        Dict with ``new_items`` and ``total_items`` counts.
    """
    config = Config.from_env()
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    try:
        result = create_watcher(config).run()
        logger.info(
            "Run complete: %d new items, %d total items",
            result["new_items"], result["total_items"],
        )
        return result
    except Exception:
        logger.exception("Fatal error during watcher execution")
        raise
