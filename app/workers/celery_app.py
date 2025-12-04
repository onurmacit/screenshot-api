"""
Celery Application Configuration

Configures Celery with Redis broker, task queues, and beat schedule.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.core.config import settings

# Create Celery application
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
    result_expires=3600,  # 1 hour

    # Task routing
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Broker settings
    broker_connection_retry_on_startup=True,
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

