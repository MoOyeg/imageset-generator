"""
Scheduler for ImageSet Automation

Manages scheduling of automation runs based on monthly execution windows.
Supports running in the last or second-to-last week of the month.
"""

import os
import sys
import logging
import calendar
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
import pytz

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logging.warning("APScheduler not available, install with: pip install apscheduler")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.engine import AutomationEngine, load_config

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Manages scheduled execution of automation"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize scheduler

        Args:
            config: Complete automation configuration
        """
        if not APSCHEDULER_AVAILABLE:
            raise ImportError("APScheduler is required for scheduling")

        self.config = config
        self.scheduler_config = config.get('scheduler', {})

        if not self.scheduler_config.get('enabled', False):
            logger.warning("Scheduler is not enabled in configuration")

        # Create scheduler
        timezone = self.scheduler_config.get('timezone', 'UTC')
        self.scheduler = BackgroundScheduler(timezone=timezone)

        # Add event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)

        # Create automation engine
        self.engine = AutomationEngine(config)

    def start(self):
        """Start the scheduler"""
        if not self.scheduler_config.get('enabled', False):
            logger.info("Scheduler is disabled, not starting")
            return

        execution_window = self.scheduler_config.get('execution_window', 'last-week')
        day_of_week = self.scheduler_config.get('day_of_week', 1)  # Tuesday
        time_str = self.scheduler_config.get('time', '02:00')

        # Parse time
        hour, minute = map(int, time_str.split(':'))

        logger.info(f"Configuring scheduler: window={execution_window}, day={day_of_week}, time={time_str}")

        if execution_window == 'last-week':
            # Days 22-31 of month
            self._schedule_last_week(day_of_week, hour, minute)

        elif execution_window == 'second-to-last-week':
            # Days 15-21 of month
            self._schedule_second_to_last_week(day_of_week, hour, minute)

        elif execution_window == 'both':
            # Both windows
            self._schedule_last_week(day_of_week, hour, minute)
            self._schedule_second_to_last_week(day_of_week, hour, minute)

        else:
            logger.error(f"Unknown execution window: {execution_window}")
            return

        # Start scheduler
        self.scheduler.start()
        logger.info("Scheduler started")

        # Log next run times
        self._log_next_runs()

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def run_now(self) -> Dict[str, Any]:
        """
        Run automation immediately (manual trigger)

        Returns:
            Execution results
        """
        logger.info("Manual automation trigger")
        return self._run_automation()

    def _schedule_last_week(self, day_of_week: int, hour: int, minute: int):
        """Schedule for last week of month (days 22-31)"""
        # Create cron trigger for specific day of week in days 22-31
        trigger = CronTrigger(
            day='22-31',
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone=self.scheduler_config.get('timezone', 'UTC')
        )

        self.scheduler.add_job(
            func=self._run_with_window_check,
            trigger=trigger,
            args=['last-week'],
            id='automation-last-week',
            name='ImageSet Automation (Last Week)',
            replace_existing=True
        )

        logger.info(f"Scheduled for last week: day_of_week={day_of_week}, time={hour:02d}:{minute:02d}")

    def _schedule_second_to_last_week(self, day_of_week: int, hour: int, minute: int):
        """Schedule for second-to-last week (days 15-21)"""
        trigger = CronTrigger(
            day='15-21',
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone=self.scheduler_config.get('timezone', 'UTC')
        )

        self.scheduler.add_job(
            func=self._run_with_window_check,
            trigger=trigger,
            args=['second-to-last-week'],
            id='automation-second-to-last-week',
            name='ImageSet Automation (Second-to-Last Week)',
            replace_existing=True
        )

        logger.info(f"Scheduled for second-to-last week: day_of_week={day_of_week}, time={hour:02d}:{minute:02d}")

    def _run_with_window_check(self, expected_window: str):
        """
        Run automation with additional window validation

        This ensures we're truly in the expected window, accounting for
        month variations (28-31 days).

        Args:
            expected_window: Expected execution window
        """
        now = datetime.now(pytz.timezone(self.scheduler_config.get('timezone', 'UTC')))
        current_window = self._get_current_window(now)

        logger.info(f"Scheduled run triggered: expected={expected_window}, current={current_window}")

        # Validate we're in the expected window
        if expected_window == 'last-week' and current_window != 'last-week':
            logger.warning("Not in last week, skipping execution")
            return

        if expected_window == 'second-to-last-week' and current_window != 'second-to-last-week':
            logger.warning("Not in second-to-last week, skipping execution")
            return

        # Execute automation
        self._run_automation()

    def _get_current_window(self, dt: datetime) -> str:
        """
        Determine which execution window we're currently in

        Args:
            dt: Current datetime

        Returns:
            'last-week', 'second-to-last-week', or 'neither'
        """
        day = dt.day
        _, last_day = calendar.monthrange(dt.year, dt.month)

        # Last week: last 10 days of month
        if day >= last_day - 9:
            return 'last-week'

        # Second-to-last week: days 15-21 (or adjusted for short months)
        if last_day <= 28:
            # Short month, adjust windows
            if 12 <= day <= 18:
                return 'second-to-last-week'
        else:
            if 15 <= day <= 21:
                return 'second-to-last-week'

        return 'neither'

    def _run_automation(self) -> Dict[str, Any]:
        """Execute automation engine"""
        try:
            logger.info("Starting automation execution")
            result = self.engine.run_automation()
            logger.info(f"Automation execution completed: success={result.get('success')}")
            return result

        except Exception as e:
            logger.exception(f"Automation execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def _job_executed(self, event):
        """Handle job execution event"""
        logger.info(f"Scheduled job executed: {event.job_id}")

    def _job_error(self, event):
        """Handle job error event"""
        logger.error(f"Scheduled job error: {event.job_id}, exception: {event.exception}")

    def _log_next_runs(self):
        """Log next scheduled run times"""
        jobs = self.scheduler.get_jobs()
        if not jobs:
            logger.warning("No jobs scheduled")
            return

        logger.info("Scheduled jobs:")
        for job in jobs:
            next_run = job.next_run_time
            if next_run:
                logger.info(f"  - {job.name}: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            else:
                logger.info(f"  - {job.name}: Not scheduled")

    def get_schedule_info(self) -> Dict[str, Any]:
        """
        Get information about scheduled jobs

        Returns:
            Schedule information dictionary
        """
        jobs = self.scheduler.get_jobs()
        now = datetime.now(pytz.timezone(self.scheduler_config.get('timezone', 'UTC')))

        info = {
            "enabled": self.scheduler_config.get('enabled', False),
            "running": self.scheduler.running,
            "timezone": self.scheduler_config.get('timezone', 'UTC'),
            "execution_window": self.scheduler_config.get('execution_window'),
            "current_window": self._get_current_window(now),
            "current_time": now.isoformat(),
            "jobs": []
        }

        for job in jobs:
            job_info = {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
            }
            info["jobs"].append(job_info)

        return info


def main():
    """Main entry point for scheduler"""
    import argparse
    import signal
    import time

    parser = argparse.ArgumentParser(description='ImageSet Automation Scheduler')
    parser.add_argument(
        '--config',
        default='automation/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    parser.add_argument(
        '--run-now',
        action='store_true',
        help='Run automation immediately instead of scheduling'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration
    config = load_config(args.config)

    # Create scheduler
    scheduler = AutomationScheduler(config)

    if args.run_now:
        # Run immediately
        result = scheduler.run_now()
        print(f"\nExecution result:")
        import json
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get('success') else 1)

    # Start scheduler
    scheduler.start()

    # Print schedule info
    info = scheduler.get_schedule_info()
    logger.info(f"Schedule info: {info}")

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep running
    logger.info("Scheduler running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == '__main__':
    main()
