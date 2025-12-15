# main.py
import time
import subprocess
import sys

INTERVAL_HOURS = 6
INTERVAL_SECONDS = INTERVAL_HOURS * 3600

def run(cmd):
    print(f"Running: {cmd}")
    subprocess.run([sys.executable] + cmd, check=True)

while True:
    try:
        run(["extract_data.py"])
        run(["json_to_sqlite.py"])
        print("Pipeline completed successfully.")
    except Exception as e:
        print(f"Pipeline error: {e}")

    print(f"Sleeping for {INTERVAL_HOURS} hours...")
    time.sleep(INTERVAL_SECONDS)