#!/usr/bin/env python3
import sys

# Check Python version (3.11+ recommended, 3.9+ minimum)
if sys.version_info < (3, 9):
    print("Error: This application requires Python 3.9 or higher.")
    print(f"You are using Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)
elif sys.version_info < (3, 11):
    print("WARNING: Python 3.11+ is recommended for optimal performance.")
    print(f"You are using Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print("The application will continue, but you may encounter compatibility issues.\n")

import threading
import socket
from server import app, socketio
from whiteboard import run_tkinter

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    host_ip = get_local_ip()
    print(f"Starting server on {host_ip}")
    
    # Start Flask-SocketIO server in a separate thread
    flask_thread = threading.Thread(
        target=lambda: socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run Tkinter in the main thread (required on macOS)
    run_tkinter(host_ip)
