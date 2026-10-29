"""
Optional in-process scheduler (set ENABLE_SCHEDULER=true). Convenient for a demo; for a real deployment with
several server processes prefer cron + `flask jobs ...` so each job fires once.
"""
import atexit

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.jobs import JOBS, run_job


def start_scheduler(app):
    """Starts the background scheduler and returns it, or returns None if ENABLE_SCHEDULER is off."""
    if not app.config.get("ENABLE_SCHEDULER"):
        return None

    scheduler = BackgroundScheduler(timezone=app.config.get("SOCIETY_TIMEZONE", "Asia/Kolkata"))

    def runner(name):
        def run():
            with app.app_context():
                try:
                    run_job(name, JOBS[name])
                except Exception:
                    app.logger.exception("Scheduled job %s failed", name)   # recorded in job_runs too
        return run

    scheduler.add_job(runner("chat_cleanup"), CronTrigger(day_of_week="sun", hour=0, minute=0), id="chat_cleanup", replace_existing=True)
    scheduler.add_job(runner("escalation"), CronTrigger(hour=9, minute=0), id="escalation", replace_existing=True)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)
    app.logger.info("Scheduler started: chat cleanup Sundays 00:00, escalation daily 09:00 (%s)", scheduler.timezone)
    return scheduler
