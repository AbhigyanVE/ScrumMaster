# main_for_server.py
import subprocess
import time
import sys
import os
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# ============================================================
# CONFIGURATION
# ============================================================

INTERVAL_HOURS = 6
INTERVAL_SECONDS = INTERVAL_HOURS * 3600

EXTRACT_SCRIPT = "extract_data.py"
TRANSFORM_SCRIPT = "json_to_sqlite.py"

LOG_DIR = "details"
EVENT_LOG_FILE = "event.log"

os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# LOGGING: EVENT LOGGER (HIGH LEVEL)
# ============================================================

event_logger = logging.getLogger("event_logger")
event_logger.setLevel(logging.INFO)

event_handler = RotatingFileHandler(
    EVENT_LOG_FILE,
    maxBytes=5 * 1024 * 1024,   # 5 MB
    backupCount=5
)
event_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

event_logger.addHandler(event_handler)

event_logger.info("=" * 60)
event_logger.info("AI Scrum Master Server Pipeline Started")
event_logger.info("=" * 60)

# ============================================================
# REDIRECT STDOUT / STDERR TO LOGS (CRITICAL)
# ============================================================

class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        if message and message.strip():
            self.logger.log(self.level, message.strip())

    def flush(self):
        pass

sys.stdout = StreamToLogger(event_logger, logging.INFO)
sys.stderr = StreamToLogger(event_logger, logging.ERROR)

# ============================================================
# DETAIL LOGGER (PER-CYCLE LOG FILE)
# ============================================================

def setup_detail_logger():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOG_DIR, f"info_{timestamp}.log")

    logger = logging.getLogger("detail_logger")
    logger.setLevel(logging.INFO)

    # Remove old handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # Console (captured by PM2)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S")
    )

    # File handler
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("------------------------------------------------------------")
    logger.info("New pipeline cycle started")
    logger.info(f"Detailed log file: {log_path}")
    logger.info("------------------------------------------------------------")

    return logger

# ============================================================
# SCRIPT EXECUTION
# ============================================================

def run_script(script_name, logger):
    event_logger.info(f"Event: Running {script_name}")
    start_time = time.time()

    try:
        process = subprocess.Popen(
            [sys.executable, script_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        for line in process.stdout:
            logger.info(f"[OUT] {line.strip()}")

        stderr = process.stderr.read()
        if stderr:
            for line in stderr.splitlines():
                logger.error(f"[ERR] {line}")

        process.wait()
        duration = time.time() - start_time

        if process.returncode == 0:
            event_logger.info(
                f"Status: {script_name} completed successfully in {duration:.2f}s"
            )
            return True
        else:
            event_logger.error(
                f"Status: {script_name} failed with exit code {process.returncode}"
            )
            return False

    except Exception as e:
        logger.exception(f"Unhandled exception while running {script_name}")
        event_logger.error(f"Status: {script_name} crashed")
        return False

# ============================================================
# MAIN LOOP (PM2 SAFE)
# ============================================================

while True:
    detail_logger = setup_detail_logger()
    event_logger.info("Pipeline: Cycle started")

    try:
        if run_script(EXTRACT_SCRIPT, detail_logger):
            if run_script(TRANSFORM_SCRIPT, detail_logger):
                detail_logger.info("Pipeline completed successfully.")
                event_logger.info("Pipeline: Cycle completed successfully")
            else:
                detail_logger.error("json_to_sqlite.py failed. Cycle aborted.")
                event_logger.error("Pipeline: Transformation failed")
        else:
            detail_logger.error("extract_data.py failed. Cycle aborted.")
            event_logger.error("Pipeline: Extraction failed")

    except Exception:
        detail_logger.exception("Pipeline crashed unexpectedly")
        event_logger.error("Pipeline: Unexpected crash")

    next_run_time = datetime.now() + timedelta(seconds=INTERVAL_SECONDS)
    event_logger.info(
        f"Scheduler: Next run scheduled at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    detail_logger.info(f"Sleeping for {INTERVAL_HOURS} hours...")
    time.sleep(INTERVAL_SECONDS)
