import sys
import os
import traceback

log_file = "verification_log.txt"

def log(msg):
    print(msg)
    with open(log_file, "a") as f:
        f.write(msg + "\n")

# Add server directory to path
sys.path.append(os.path.join(os.getcwd(), 'server'))

log("Starting verification...")

log("Importing voice_chat...")
try:
    import voice_chat
    log("voice_chat imported successfully.")
except Exception as e:
    log(f"FAILED to import voice_chat: {e}")
    log(traceback.format_exc())
    # Don't exit yet, try others

log("Importing connection_manager...")
try:
    import connection_manager
    log("connection_manager imported successfully.")
except Exception as e:
    log(f"FAILED to import connection_manager: {e}")
    log(traceback.format_exc())

log("Verification complete.")
