import threading
import sys
import socket
from server import app, socketio
from whiteboard import run_tkinter

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def run_flask(host_ip):
    # Try to use eventlet for better stability if installed
    try:
        import eventlet
        from eventlet import wsgi
        print("Using Eventlet for server stability")
        eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)
    except ImportError:
        print("Eventlet not found, falling back to standard Flask server")
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=False, 
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )

if __name__ == "__main__":
    host_ip = get_local_ip()
    print(f"Starting server on {host_ip}")

    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, args=(host_ip,))
    flask_thread.daemon = True
    flask_thread.start()

    # Run Tkinter GUI in the main thread (Tkinter must be in main thread)
    run_tkinter(host_ip)
