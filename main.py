import subprocess
import time
import os
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import threading
from functools import wraps

# === CONFIGURATION ===
# Time interval for the data refresh cycle (in seconds)
# 12 hours = 12 * 60 * 60 = 43200 seconds
REFRESH_INTERVAL_SECONDS = 600  # Set to 10 mins
# Use a shorter interval for initial testing (e.g., 60 seconds)
# REFRESH_INTERVAL_SECONDS = 60 

# File paths
EXTRACT_SCRIPT = "extract_data.py"
TRANSFORM_SCRIPT = "json_to_sqlite.py"
APP_SCRIPT = "app.py"
LOG_DIR = "details"
EVENT_LOG_FILE = "event.log"

# Global to hold the Streamlit process object
streamlit_process = None

# --- Setup Logging ---

# Create log directory if it doesn't exist
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 1. Event Log (Simple, High-Level Events)
event_logger = logging.getLogger('event_logger')
event_logger.setLevel(logging.INFO)
event_handler = logging.FileHandler(EVENT_LOG_FILE, mode='a')
event_formatter = logging.Formatter('%(asctime)s - %(message)s')
event_handler.setFormatter(event_formatter)
event_logger.addHandler(event_handler)
event_logger.info("=" * 60)
event_logger.info("AI Scrum Master Pipeline Initializing")
event_logger.info("=" * 60)

# 2. Detail Log (Full output from executed scripts)
# This logger will be configured dynamically for each run
def setup_detail_logger():
    """Sets up a new detail logger for each run with a unique timestamped file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_log_file = os.path.join(LOG_DIR, f"info_{timestamp}.log")
    
    # Create logger and set level to INFO
    detail_logger = logging.getLogger('detail_logger')
    detail_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to prevent multiple logs
    for handler in detail_logger.handlers[:]:
        detail_logger.removeHandler(handler)
        
    # Console handler (to show output in the terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    detail_logger.addHandler(console_handler)
    
    # File handler (to save all output to the timestamped file)
    file_handler = logging.FileHandler(detail_log_file, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    detail_logger.addHandler(file_handler)
    
    detail_logger.info(f"--- Starting new cycle. Logging all output to {detail_log_file} ---")
    return detail_logger

# --- Process Management and Execution Functions ---

def kill_streamlit():
    """Tries to gracefully terminate the running Streamlit process."""
    global streamlit_process
    if streamlit_process and streamlit_process.poll() is None:
        event_logger.info("Event: Killing running Streamlit app...")
        detail_logger = logging.getLogger('detail_logger')
        
        try:
            # Send a termination signal
            os.kill(streamlit_process.pid, signal.SIGTERM)
            time.sleep(5)  # Give it a moment to shut down
            
            # If still alive, force kill
            if streamlit_process.poll() is None:
                os.kill(streamlit_process.pid, signal.SIGKILL)
                detail_logger.info(f"Streamlit process (PID: {streamlit_process.pid}) force-killed.")
            else:
                detail_logger.info(f"Streamlit process (PID: {streamlit_process.pid}) gracefully terminated.")
                
            streamlit_process = None
            event_logger.info("Status: Streamlit killed successfully.")
            return True
        except Exception as e:
            detail_logger.error(f"Error while killing Streamlit process: {e}")
            event_logger.error("Status: Failed to kill Streamlit.")
            return False
    return True # Not running or already dead

def run_script(script_name):
    """Executes a Python script and logs its output."""
    event_logger.info(f"Event: Starting {script_name}...")
    detail_logger = logging.getLogger('detail_logger')
    
    start_time = time.time()
    try:
        # Use subprocess.run to execute the script and capture output
        # Setting shell=True can be dangerous, prefer passing a list
        command = [sys.executable, script_name]
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Use text mode for reading output
        )
        
        # Log output line by line as it comes
        for line in process.stdout:
            detail_logger.info(f"[OUT] {line.strip()}")
            
        # Wait for the process to complete and get the return code
        process.wait()
        
        # Log stderr (errors or warnings from the script)
        stderr_output = process.stderr.read().strip()
        if stderr_output:
            for line in stderr_output.split('\n'):
                detail_logger.error(f"[ERR] {line.strip()}")
            
        return_code = process.returncode
        end_time = time.time()
        
        if return_code == 0:
            event_logger.info(f"Status: {script_name} completed successfully in {end_time - start_time:.2f}s.")
            return True
        else:
            event_logger.error(f"Status: {script_name} failed with return code {return_code}.")
            detail_logger.error(f"Script failed: {script_name} returned non-zero exit code.")
            return False
            
    except FileNotFoundError:
        detail_logger.error(f"Error: {script_name} not found. Check file path.")
        event_logger.error(f"Status: {script_name} failed (File not found).")
        return False
    except Exception as e:
        detail_logger.error(f"Unexpected error during {script_name} execution: {e}")
        event_logger.error(f"Status: {script_name} failed (Unexpected error).")
        return False

def start_streamlit():
    """Starts the Streamlit application in a new process."""
    global streamlit_process
    event_logger.info("Event: Starting Streamlit app (Headless mode)...")
    detail_logger = logging.getLogger('detail_logger')
    
    try:
        # Command to run Streamlit with flags to prevent automatic browser opening
        command = [
            sys.executable, 
            "-m", 
            "streamlit", 
            "run", 
            APP_SCRIPT,
            "--server.headless", "true",  # CRITICAL: Prevents browser from launching
            "--browser.gatherUsageStats", "false" # Optional: Speeds up launch slightly
        ]
        
        # Start the process without waiting, and redirect stdout/stderr
        streamlit_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        detail_logger.info(f"Streamlit app started with PID: {streamlit_process.pid}")
        event_logger.info("Status: Streamlit started successfully.")
        
        # Log a few lines of Streamlit's initial output to find the URL
        detail_logger.info("Streamlit initial output (logging first 5 lines):")
        for i, line in enumerate(streamlit_process.stdout):
            detail_logger.info(f"[ST_OUT] {line.strip()}")
            if i >= 4: # Log 5 lines
                break
                
        # NOTE: You will still need to manually check the terminal output 
        # for the 'Network URL' to access the app in your browser.
        
        return True
    except Exception as e:
        detail_logger.error(f"Failed to start Streamlit: {e}")
        event_logger.error("Status: Failed to start Streamlit.")
        return False

# --- Main Scheduling Logic ---

def data_refresh_cycle():
    """
    The core function that runs the data extraction, transformation, 
    and application restart sequence.
    """
    # Set up the detail logger for this specific cycle
    global detail_logger
    detail_logger = setup_detail_logger()
    
    detail_logger.info("--- Data Refresh Cycle Started ---")
    
    # 1. Kill the Streamlit app
    kill_streamlit()
    
    # 2. Run extract_data.py
    if run_script(EXTRACT_SCRIPT):
        # 3. Run json_to_sqlite.py (only if extraction was successful)
        if run_script(TRANSFORM_SCRIPT):
            # 4. Restart app.py
            if start_streamlit():
                detail_logger.info("--- Cycle Complete: New data is live. ---")
            else:
                detail_logger.error("--- Cycle Aborted: Failed to restart app.py ---")
        else:
            detail_logger.error("--- Cycle Aborted: json_to_sqlite.py failed. Skipping app restart. ---")
    else:
        detail_logger.error("--- Cycle Aborted: extract_data.py failed. Skipping transformation and app restart. ---")
    
    # Schedule the next run
    schedule_next_run()

def schedule_next_run():
    """Schedules the data_refresh_cycle function to run after the interval."""
    # Use threading.Timer to run the cycle in a new thread after the interval
    timer = threading.Timer(REFRESH_INTERVAL_SECONDS, data_refresh_cycle)
    timer.daemon = True # Allows the main program to exit even if the timer is running
    timer.start()
    
    # Calculate next run time for logging
    # next_run_time = datetime.now() + datetime.timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    next_run_time = datetime.now() + timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    event_logger.info(f"Scheduler: Next refresh cycle scheduled for: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")

def cleanup_and_exit(signum, frame):
    """Handles graceful exit, triggered by SIGINT (Ctrl+C)."""
    print("\n\n[MAIN] Received shutdown signal. Starting cleanup...")
    event_logger.info("Event: Received shutdown signal (Ctrl+C).")
    
    # Attempt to kill the Streamlit process before exiting
    kill_streamlit()
    
    event_logger.info("Event: Main program exiting.")
    sys.exit(0)

# --- Main Execution Block ---

if __name__ == "__main__":
    # Register the cleanup handler for Ctrl+C
    signal.signal(signal.SIGINT, cleanup_and_exit)
    
    print("=" * 60)
    print(f"AI Scrum Master Pipeline Manager (Interval: {REFRESH_INTERVAL_SECONDS/3600:.2f} hours)")
    print("Press Ctrl+C to stop the application gracefully.")
    print("=" * 60)
    
    # Perform the initial setup run immediately
    data_refresh_cycle()
    
    # Keep the main thread alive indefinitely to allow the scheduler to run
    try:
        while True:
            time.sleep(1)
    except SystemExit:
        pass # Allow the cleanup_and_exit to handle exit
    except Exception as e:
        event_logger.error(f"Main loop encountered an unexpected error: {e}")
        cleanup_and_exit(None, None) # Trigger cleanup