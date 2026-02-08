from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from PIL import Image
import base64
import io
import time
import queue
import threading

# Flask App for Whiteboard
app = Flask(__name__)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    ping_timeout=120,
    ping_interval=25,
    async_mode='threading',  # Use gevent for better WebSocket stability
    logger=False,
    engineio_logger=False
)

# Queue for coordinates (bounded to prevent memory leak)
coordinates_queue = queue.Queue(maxsize=1000)

# Connection management
connection_requests = queue.Queue()
connected_clients = set()
connected_clients_lock = threading.Lock()  # Thread-safe access

# Client viewports information
client_viewports = {}
client_viewports_lock = threading.Lock()  # Thread-safe access

@app.route("/")
def index():
    return "Server is running."

@app.route("/upload_image", methods=["POST"])
def upload_image():
    """Handle image upload."""
    file = request.files.get("image")
    if file:
        file.save("uploaded_image.png")
        # Convert to base64 and emit
        with open("uploaded_image.png", "rb") as img_file:
            img_bytes = img_file.read()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            # Get image dimensions
            img = Image.open("uploaded_image.png")
            width, height = img.size
            socketio.emit("new_image", {
                "image_data": img_base64,
                "canvas_width": width,
                "canvas_height": height
            })
        return jsonify({"message": "Image uploaded successfully"}), 200
    return jsonify({"message": "No image uploaded"}), 400

@socketio.on("connect")
def handle_connect():
    """Handle client connection request."""
    client_id = request.sid
    client_ip = request.remote_addr
    print(f"Connection request from {client_ip} (ID: {client_id})")
    
    # Auto-accept for view-only mode.
    # We do NOT add to connection_requests here.
    # Requests are only added when they ask for edit permission (Reason: User Requirement)
    
    # Connection is pending until approved
    return True

@socketio.on("request_current_state")
def handle_request_current_state():
    """Send current PDF state to a newly connected client."""
    client_id = request.sid
    print(f"Client {client_id} requested current state")
    # The whiteboard will handle sending current PDF when this event is received

@socketio.on("request_edit_permission")
def handle_edit_permission(data):
    """Handle explicit edit permission request (Raise Hand)."""
    client_id = request.sid
    client_ip = request.remote_addr
    question = data.get("question", "Requesting access")
    
    print(f"Edit permission request from {client_id}: {question}")
    print(f"Current queue size before adding: {connection_requests.qsize()}")
    
    # Add to connection request queue
    connection_requests.put({
        "client_id": client_id,
        "client_ip": client_ip,
        "timestamp": time.time(),
        "status": "pending",
        "question": question
    })
    
    print(f"Request added to queue. New queue size: {connection_requests.qsize()}")
@socketio.on("allow_student")
def allowStudent(client_id):
    socketio.emit("allow_student", {"allowed_sid": client_id})

@socketio.on("send_coordinates")
def handle_coordinates(data):
    """Handle incoming coordinates from clients."""
    client_id = request.sid
    
    # Only process if client is approved (thread-safe check)
    with connected_clients_lock:
        is_approved = client_id in connected_clients
    
    if is_approved:
        try:
            coordinates_queue.put(data, block=False)
        except queue.Full:
            print(f"Warning: Coordinate queue full, dropping packet from {client_id}")
            return
        
        # Broadcast to all other approved clients
        socketio.emit("coordinate_update", data, skip_sid=request.sid)
    else:
        print(f"Rejected coordinates from unapproved client {client_id}")

@socketio.on("register_viewport")
def handle_viewport_registration(data):
    """Handle client viewport registration."""
    client_id = request.sid
    
    # Only process if client is approved (thread-safe check)
    with connected_clients_lock:
        is_approved = client_id in connected_clients
    
    if is_approved:
        width = data.get("width", 0)
        height = data.get("height", 0)
        
        with client_viewports_lock:
            client_viewports[client_id] = {"width": width, "height": height}

@socketio.on("client_disconnect")
def handle_client_disconnect():
    """Handle client-initiated disconnect (Exit button)."""
    client_id = request.sid
    print(f"Client {client_id} requested disconnect")
    
    # Remove from connected clients (thread-safe)
    with connected_clients_lock:
        if client_id in connected_clients:
            connected_clients.remove(client_id)
            print(f"Removed {client_id} from connected_clients")
    
    # Remove from viewports (thread-safe)
    with client_viewports_lock:
        if client_id in client_viewports:
            del client_viewports[client_id]
    
    # Disconnect voice chat
    try:
        from whiteboard import whiteboard_instance
        if whiteboard_instance and whiteboard_instance.voice_chat:
            whiteboard_instance.voice_chat.force_disconnect_client()
            print("Voice chat disconnected")
    except Exception as e:
        print(f"Error disconnecting voice: {e}")

@socketio.on("disconnect")
def handle_disconnect():
    """Clean up when client disconnects."""
    client_id = request.sid
    
    # Clean up viewport (thread-safe)
    with client_viewports_lock:
        if client_id in client_viewports:
            del client_viewports[client_id]
    
    # Remove from connected clients (thread-safe)
    with connected_clients_lock:
        if client_id in connected_clients:
            connected_clients.remove(client_id)
            print(f"Client {client_id} disconnected, removed from approved clients")