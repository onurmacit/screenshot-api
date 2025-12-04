"""
Celery workers module

This module contains all Celery task definitions for background processing.
"""

from app.workers.celery_app import celery_app, get_queue_for_plan, get_priority_for_plan
from app.workers.render_tasks import process_screenshot, process_pdf, queue_render_job
from app.workers.webhook_tasks import send_webhook, send_job_webhook, trigger_event_webhooks
from app.workers.maintenance_tasks import (
    cleanup_expired_files,
    calculate_daily_usage,
    cleanup_old_audit_logs,
)
from app.workers.billing_tasks import (
    sync_stripe_subscriptions,
    check_usage_limits,
    process_overage_billing,
)

__all__ = [
    # Celery app
    "celery_app",
    "get_queue_for_plan",
    "get_priority_for_plan",

    # Render tasks
    "process_screenshot",
    "process_pdf",
    "queue_render_job",

    # Webhook tasks
    "send_webhook",
    "send_job_webhook",
    "trigger_event_webhooks",

    # Maintenance tasks
    "cleanup_expired_files",
    "calculate_daily_usage",
    "cleanup_old_audit_logs",

    # Billing tasks
    "sync_stripe_subscriptions",
    "check_usage_limits",
    "process_overage_billing",
]
