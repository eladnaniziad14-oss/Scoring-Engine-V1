import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from orchestration.jobs.run_micros_job import run as micros_job
from orchestration.jobs.run_social_job import run as social_job
from orchestration.jobs.run_macros_job import run as macros_job
from orchestration.jobs.run_sector_job import run as sector_job
from orchestration.jobs.run_volatility_job import run as vol_job

logging.basicConfig(level=logging.INFO)
scheduler = BlockingScheduler()

# ---------------- SCHEDULES ----------------
scheduler.add_job(micros_job, "interval", minutes=15)
scheduler.add_job(social_job, "interval", minutes=10)
scheduler.add_job(macros_job, "cron", hour=0)       # daily macro refresh
scheduler.add_job(sector_job, "cron", hour="*/4")   # update every 4 hours
scheduler.add_job(vol_job, "interval", minutes=30)

# -------------------------------------------

if __name__ == "__main__":
    logging.info("🚀 Scheduler started — sentiment automation online.")
    scheduler.start()
