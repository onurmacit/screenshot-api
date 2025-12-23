"""
Celery Application Configuration

Configures Celery with Redis broker, task queues, and beat schedule.
Includes worker lifecycle management for proper resource cleanup.
"""

import asyncio
import atexit
import threading

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
from kombu import Exchange, Queue

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# Event Loop Management
# =============================================================================

# Thread-local storage for event loop
_thread_local = threading.local()
_worker_initialized = False
_cleanup_lock = threading.Lock()


def get_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get or create event loop for current thread.
    
    Returns:
        Event loop for current thread
    """
    if not hasattr(_thread_local, "loop") or _thread_local.loop is None:
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
    return _thread_local.loop


def run_async(coro):
    """
    Run async coroutine in sync context.
    
    Uses thread-local event loop to avoid conflicts.
    
    Args:
        coro: Async coroutine to run
        
    Returns:
        Result of the coroutine
    """
    loop = get_event_loop()
    return loop.run_until_complete(coro)


def cleanup_event_loop():
    """Clean up thread-local event loop."""
    if hasattr(_thread_local, "loop") and _thread_local.loop is not None:
        try:
            loop = _thread_local.loop
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Run until all tasks are cancelled
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            loop.close()
        except Exception as e:
            logger.warning("Error cleaning up event loop", error=str(e))
        finally:
            _thread_local.loop = None


# =============================================================================
# Worker Lifecycle Signals
# =============================================================================

@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize worker process.
    
    Called when a new worker process starts.
    Sets up event loop and initializes browser pool.
    """
    global _worker_initialized

    logger.info("Initializing Celery worker process")

    # Create event loop for this worker
    loop = get_event_loop()

    # Initialize browser pool for render workers
    try:
        from app.services.render_service import browser_pool
        loop.run_until_complete(browser_pool.initialize())
        logger.info("Browser pool initialized for worker")
    except Exception as e:
        logger.warning("Could not initialize browser pool", error=str(e))

    _worker_initialized = True
    logger.info("Celery worker process initialized")


@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """
    Clean up worker process on shutdown.
    
    Called when worker process is shutting down.
    Closes browser pool and cleans up resources.
    """
    global _worker_initialized

    with _cleanup_lock:
        if not _worker_initialized:
            return

        logger.info("Shutting down Celery worker process")

        # Close browser pool
        try:
            from app.services.render_service import browser_pool
            loop = get_event_loop()
            loop.run_until_complete(browser_pool.close())
            logger.info("Browser pool closed")
        except Exception as e:
            logger.warning("Error closing browser pool", error=str(e))

        # Clean up event loop
        cleanup_event_loop()

        _worker_initialized = False
        logger.info("Celery worker process shutdown complete")


# Register cleanup on process exit
atexit.register(lambda: shutdown_worker_process(sender=None))


# =============================================================================
# Celery Application
# =============================================================================

celery_app = Celery(
    "screenshot_api",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.render_tasks",
        "app.workers.webhook_tasks",
        "app.workers.maintenance_tasks",
        "app.workers.billing_tasks",
    ],
)

# =============================================================================
# Celery Configuration
# =============================================================================

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task tracking
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_concurrency=4,

    # Result backend settings
    result_expires=300,  # 5 minutes (was 1 hour) - reduces Redis storage

    # Task routing
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Broker settings
    broker_connection_retry_on_startup=True,
    
    # ==========================================================================
    # Redis Command Optimization Settings
    # ==========================================================================
    
    # Disable worker gossip - reduces Redis PUBLISH/SUBSCRIBE commands
    worker_enable_remote_control=False,
    
    # Disable mingle - workers don't need to sync with each other
    # Saves ~10-20 Redis commands per worker on startup
    worker_disable_tracebacks=True,
    
    # Increase heartbeat interval (default 2s → 30s)
    # Reduces heartbeat commands by 93%
    broker_heartbeat=30,
    
    # Disable task events unless needed for monitoring
    # Saves PUBLISH commands for every task state change
    worker_send_task_events=False,
    task_send_sent_event=False,
    
    # Use transient queues - no persistence needed
    task_create_missing_queues=True,
    
    # Broker pool limit - reduce connection overhead
    broker_pool_limit=3,
)

# =============================================================================
# Queue Definitions
# =============================================================================

# Define exchanges
default_exchange = Exchange("default", type="direct")
priority_exchange = Exchange("priority", type="direct")

# Define queues
celery_app.conf.task_queues = (
    # High priority queue - Pro and Business plans
    Queue(
        "high_priority",
        exchange=priority_exchange,
        routing_key="high",
        queue_arguments={
            "x-max-priority": 10,
        },
    ),
    # Default queue - Starter plan
    Queue(
        "default",
        exchange=default_exchange,
        routing_key="default",
    ),
    # Low priority queue - Free tier
    Queue(
        "low_priority",
        exchange=priority_exchange,
        routing_key="low",
    ),
    # Webhooks queue
    Queue(
        "webhooks",
        exchange=default_exchange,
        routing_key="webhooks",
    ),
    # Cleanup/maintenance queue
    Queue(
        "cleanup",
        exchange=default_exchange,
        routing_key="cleanup",
    ),
    # Billing queue
    Queue(
        "billing",
        exchange=default_exchange,
        routing_key="billing",
    ),
)

# =============================================================================
# Task Routing
# =============================================================================

celery_app.conf.task_routes = {
    # Render tasks - routed based on plan (set in task call)
    "app.workers.render_tasks.process_screenshot": {
        "queue": "default",
    },
    "app.workers.render_tasks.process_pdf": {
        "queue": "default",
    },

    # Webhook tasks
    "app.workers.webhook_tasks.send_webhook": {
        "queue": "webhooks",
    },
    "app.workers.webhook_tasks.send_job_webhook": {
        "queue": "webhooks",
    },

    # Maintenance tasks
    "app.workers.maintenance_tasks.cleanup_expired_files": {
        "queue": "cleanup",
    },
    "app.workers.maintenance_tasks.calculate_daily_usage": {
        "queue": "cleanup",
    },
    "app.workers.maintenance_tasks.cleanup_old_audit_logs": {
        "queue": "cleanup",
    },

    # Billing tasks
    "app.workers.billing_tasks.sync_stripe_subscriptions": {
        "queue": "billing",
    },
    "app.workers.billing_tasks.check_usage_limits": {
        "queue": "billing",
    },
}

# =============================================================================
# Beat Schedule (Periodic Tasks)
# =============================================================================

celery_app.conf.beat_schedule = {
    # Cleanup expired files every hour
    "cleanup-expired-files": {
        "task": "app.workers.maintenance_tasks.cleanup_expired_files",
        "schedule": crontab(minute=0),  # Every hour at minute 0
        "options": {
            "queue": "cleanup",
        },
    },

    # Calculate daily usage at midnight UTC
    "calculate-daily-usage": {
        "task": "app.workers.maintenance_tasks.calculate_daily_usage",
        "schedule": crontab(hour=0, minute=0),  # Midnight UTC
        "options": {
            "queue": "cleanup",
        },
    },

    # Sync Stripe subscriptions every 6 hours
    "sync-stripe-subscriptions": {
        "task": "app.workers.billing_tasks.sync_stripe_subscriptions",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        "options": {
            "queue": "billing",
        },
    },

    # Check usage limits every 15 minutes
    "check-usage-limits": {
        "task": "app.workers.billing_tasks.check_usage_limits",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
        "options": {
            "queue": "billing",
        },
    },

    # Cleanup old audit logs weekly
    "cleanup-old-audit-logs": {
        "task": "app.workers.maintenance_tasks.cleanup_old_audit_logs",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
        "options": {
            "queue": "cleanup",
        },
    },
}

# =============================================================================
# Helper Functions
# =============================================================================


def get_queue_for_plan(plan_name: str) -> str:
    """
    Get the appropriate queue name based on user's plan.

    Args:
        plan_name: User's plan name

    Returns:
        Queue name string
    """
    queue_map = {
        "business": "high_priority",
        "pro": "high_priority",
        "starter": "default",
        "free": "low_priority",
    }
    return queue_map.get(plan_name, "low_priority")


def get_priority_for_plan(plan_name: str) -> int:
    """
    Get task priority based on user's plan.

    Args:
        plan_name: User's plan name

    Returns:
        Priority integer (higher = more priority)
    """
    priority_map = {
        "business": 10,
        "pro": 8,
        "starter": 5,
        "free": 1,
    }
    return priority_map.get(plan_name, 1)
