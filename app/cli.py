import click
from flask.cli import AppGroup
from sqlalchemy import func

from app.extensions import db
from app.jobs import JOBS, run_job
from app.models.job_run import JobRun

jobs_cli = AppGroup("jobs", help="Housekeeping jobs: chat cleanup and automatic escalation.")


def _run(name):
    try:
        result = run_job(name, JOBS[name])
    except Exception as exc:
        click.echo(f"{name}: FAILED - {type(exc).__name__}: {exc}", err=True)
        raise SystemExit(1)
    click.echo(f"{name}: {result}")


@jobs_cli.command("cleanup-chats")
def cleanup_chats():
    """Delete chat transcripts older than CHAT_RETENTION_DAYS (complaints are never touched)."""
    _run("chat_cleanup")


@jobs_cli.command("escalate")
def escalate():
    """Escalate complaints nobody has responded to for ESCALATION_DAYS."""
    _run("escalation")


@jobs_cli.command("run-all")
def run_all():
    """Run every job once."""
    for name in JOBS:
        _run(name)


@jobs_cli.command("status")
def status():
    """Show the most recent run of each job."""
    for name in JOBS:
        last = JobRun.query.filter_by(job=name).order_by(JobRun.id.desc()).first()
        if last is None:
            click.echo(f"{name}: never run")
            continue
        outcome = "running/crashed" if last.ok is None else ("ok" if last.ok else "FAILED")
        click.echo(f"{name}: {outcome} at {last.started_at:%Y-%m-%d %H:%M:%S} UTC - {last.summary}")
