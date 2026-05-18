import logging
import os
import sys
import threading
import time

from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from .models import VotingSession
from .results_notifications import send_session_results_notifications


logger = logging.getLogger(__name__)

_notifier_started = False


def notify_closed_sessions_once():
    close_old_connections()

    try:
        sessions = VotingSession.objects.filter(
            active=True,
            end_datetime__lte=timezone.now(),
        ).filter(
            Q(results_email_sent=False) | Q(results_sms_sent=False)
        )

        for session in sessions:
            sent_counts = send_session_results_notifications(session)
            logger.info(
                "Checked closed voting session %s: sent %s email(s), %s SMS message(s).",
                session.id,
                sent_counts["email"],
                sent_counts["sms"],
            )
    finally:
        close_old_connections()


def _notifier_loop(interval_seconds):
    while True:
        try:
            notify_closed_sessions_once()
        except Exception:
            logger.exception("Closed-session results notifier failed.")

        time.sleep(interval_seconds)


def should_start_notifier():
    if os.environ.get("DISABLE_RESULTS_NOTIFIER", "").strip().lower() in {"1", "true", "yes"}:
        return False

    if len(sys.argv) > 1 and sys.argv[1] in {
        "check",
        "collectstatic",
        "makemigrations",
        "migrate",
        "send_results",
        "shell",
        "test",
    }:
        return False

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        return os.environ.get("RUN_MAIN") == "true"

    return True


def start_results_notifier():
    global _notifier_started

    if _notifier_started or not should_start_notifier():
        return

    interval_seconds = int(os.environ.get("RESULTS_NOTIFIER_INTERVAL_SECONDS", "30"))
    thread = threading.Thread(
        target=_notifier_loop,
        args=(interval_seconds,),
        name="closed-session-results-notifier",
        daemon=True,
    )
    thread.start()
    _notifier_started = True
    logger.info("Started closed-session results notifier every %s seconds.", interval_seconds)
