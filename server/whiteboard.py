from tkinter import Tk, Canvas, Button, filedialog, ttk, Frame, Label, StringVar, Scale, HORIZONTAL, IntVar
import time
import threading
import io
from PIL import Image, ImageTk
import base64
import fitz  # PyMuPDF for PDF handling

from voice_chat import VoiceChat
from connection_manager import ConnectionRequestPanel, ConnectedClientPanel
from server import socketio, coordinates_queue, connected_clients

class CollaborativeWhiteboard:
    def __init__(self, root, host_ip):
        self.root = root
        self.root.title("Collaborative Whiteboard with Voice Chat")
        self.host_ip = host_ip
        
        # Main frame
        self.main_frame = Frame(root)
        self.main_frame.pack(fill="both", expand=True)
        
        # Create left panel for tools and controls
        self.left_panel = Frame(self.main_frame, width=200, bg="#f0f0f0")
        self.left_panel.pack(side="left", fill="y", padx=5, pady=5)
        
        # Create right panel for canvas
        self.right_panel = Frame(self.main_frame)
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        # Canvas Setup
        self.canvas_width = 1280
        self.canvas_height = 720
        self.canvas = Canvas(self.right_panel, bg="white", width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack(fill="both", expand=True)
        
        # Initialize the voice chat
        self.voice_chat = VoiceChat(host_ip)
        
        # Create connection panel
        self.connection_frame = Frame(self.left_panel, bg="#f0f0f0")
        self.connection_frame.pack(fill="x", padx=5, pady=10)
        
        Label(self.connection_frame, text="Connection Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        # IP Display
        ip_frame = Frame(self.connection_frame, bg="#f0f0f0")
        ip_frame.pack(fill="x", pady=5)
        Label(ip_frame, text="Your IP:", bg="#f0f0f0").pack(side="left")
        Label(ip_frame, text=host_ip, bg="#f0f0f0", fg="blue").pack(side="left")
        
        # Connection Buttons
        btn_frame = Frame(self.connection_frame, bg="#f0f0f0")
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Disconnect Voice", command=self.disconnect_voice).pack(side="left", padx=2)
        
        # Status display
        ttk.Label(self.connection_frame, textvariable=self.voice_chat.status_var).pack(pady=5)
        
        # Connected clients display
        self.clients_var = StringVar()
        self.clients_var.set("Connected Clients: 0")
        ttk.Label(self.connection_frame, textvariable=self.clients_var).pack(pady=5)
        
        
        # Add connection request panel
        self.connection_request_panel = ConnectionRequestPanel(self.left_panel)
        
        # Add connected clients panel (Active Students)
        self.connected_client_panel = ConnectedClientPanel(self.left_panel)
        
        # Drawing Tools
        self.drawing_frame = Frame(self.left_panel, bg="#f0f0f0")
        self.drawing_frame.pack(fill="x", padx=5, pady=10)
        
        Label(self.drawing_frame, text="Drawing Tools", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        
        # Pen Colors
        colors_frame = Frame(self.drawing_frame, bg="#f0f0f0")
        colors_frame.pack(fill="x", pady=2)
        
        colors = [("Black", "black"), ("Blue", "blue"), ("Red", "red"), ("Green", "green")]
        for name, col in colors:
            btn = Button(colors_frame, bg=col, width=2, command=lambda c=col: self.set_pen_color(c))
            btn.pack(side="left", padx=2)
            
        # Line Width
        width_frame = Frame(self.drawing_frame, bg="#f0f0f0")
        width_frame.pack(fill="x", pady=5)
        Label(width_frame, text="Size:", bg="#f0f0f0").pack(side="left")
        Scale(width_frame, from_=1, to=10, orient=HORIZONTAL, command=self.set_line_width, bg="#f0f0f0").pack(side="left", fill="x", expand=True)

        
        # PDF Controls
        self.pdf_frame = Frame(self.left_panel, bg="#f0f0f0")
        self.pdf_frame.pack(fill="x", padx=5, pady=10)
        
        Label(self.pdf_frame, text="PDF Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        # PDF Navigation - Horizontal row
        nav_frame = Frame(self.pdf_frame, bg="#f0f0f0")
        nav_frame.pack(fill="x", pady=5)
        
        self.page_var = IntVar(value=1)
        self.total_pages_var = StringVar(value="/ 0")
        
        ttk.Button(nav_frame, text="◀", width=3, command=self.previous_page).pack(side="left", padx=2)
        Label(nav_frame, textvariable=self.page_var, bg="#f0f0f0", width=3).pack(side="left")
        Label(nav_frame, textvariable=self.total_pages_var, bg="#f0f0f0").pack(side="left")
        ttk.Button(nav_frame, text="▶", width=3, command=self.next_page).pack(side="left", padx=2)
        
        # PDF Action Buttons - Vertical stack to prevent clipping
        ttk.Button(self.pdf_frame, text="📄 Upload PDF", command=self.upload_pdf).pack(fill="x", pady=2)
        ttk.Button(self.pdf_frame, text="🗑️ Clear Annotations", command=self.clear_annotations).pack(fill="x", pady=2)
        ttk.Button(self.pdf_frame, text="❌ Clear All", command=self.clear_all).pack(fill="x", pady=2)

        
        # Drawing variables
        self.prev_x = None
        self.prev_y = None
        self.drawing = False
        self.current_image_tk = None
        self.image_width = self.canvas_width  # Default to canvas size
        self.image_height = self.canvas_height
        self.x_offset = 0
        self.y_offset = 0
        
        # PDF Variables
        self.pdf_document = None
        self.current_page = 0
        self.total_pages = 0
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)
        
        # Start the coordinate processing
        self.root.after(50, self.process_coordinates)
        # Start audio level update
        # Start connected clients counter update
        self.root.after(500, self.update_client_count)
        # Start connection request panel refresh
        self.root.after(2000, self.refresh_connection_requests)
        
        # Start the voice server automatically
        self.voice_chat.start_server()
        
        # Setup handler for sending current state to new clients
        self.setup_state_sync()
    
    def setup_state_sync(self):
        """Setup handler to send current PDF to newly connected clients."""
        from server import socketio as server_socketio
        
        @server_socketio.on("request_current_state")
        def send_current_state_to_client():
            """Send current PDF state to the requesting client."""
            from flask import request
            client_id = request.sid
            print(f"Sending current PDF state to client {client_id}")
            
            if self.pdf_document and self.total_pages > 0:
                # Re-render current page and send to this specific client
                try:
                    page = self.pdf_document[self.current_page]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Send as page image (not full PDF to save bandwidth)
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    server_socketio.emit("change_page", {
                        "page_image": img_base64,
                        "page_number": self.current_page,
                        "canvas_width": pix.width,
                        "canvas_height": pix.height
                    }, room=client_id)
                    
                    # Also send PDF metadata
                    server_socketio.emit("pdf_metadata", {
                        "total_pages": self.total_pages,
                        "current_page": self.current_page
                    }, room=client_id)
                    
                    print(f"Sent current PDF state to {client_id}: page {self.current_page+1}/{self.total_pages}")
                except Exception as e:
                    print(f"Error sending current state to {client_id}: {e}")
            else:
                print(f"No PDF loaded, nothing to send to {client_id}")
    
    def refresh_connection_requests(self):
        """Refresh the connection request panel."""
        self.connection_request_panel.refresh_requests()
        self.root.after(4000, self.refresh_connection_requests)
    
    def update_client_count(self):
        """Update the connected clients counter"""
        count = len(connected_clients)
        self.clients_var.set(f"Connected Clients: {count}")
        self.root.after(2000, self.update_client_count)
    
    def disconnect_voice(self):
        """Disconnect the voice chat"""
        self.voice_chat.disconnect()
        # Start the server again after a short delay
        self.root.after(1000, self.voice_chat.start_server)
    
    def set_pen_color(self, color):
        """Set the pen color"""
        self.pen_color = color
    
    def set_line_width(self, width):
        """Set the line width"""
        self.line_width = int(float(width))
    
    def start_draw(self, event):
        """Start drawing on mouse press"""
        self.drawing = True
        # Store current position
        x, y = event.x, event.y
        
        # Convert to normalized coordinates (0-1)
        norm_x = (x - self.x_offset) / self.image_width if self.image_width > 0 else 0
        norm_y = (y - self.y_offset) / self.image_height if self.image_height > 0 else 0
        
        # Bound coordinates to valid range
        norm_x = max(0, min(1, norm_x))
        norm_y = max(0, min(1, norm_y))
        
        # Reset previous point
        self.prev_x = x
        self.prev_y = y
        
        # Draw a point
        self.canvas.create_oval(
            x - self.line_width / 2, y - self.line_width / 2,
            x + self.line_width / 2, y + self.line_width / 2,
            fill=self.pen_color, outline=self.pen_color, tags="annotation"
        )
        
        # Send to Flask server
        data = {
            "x": norm_x,
            "y": norm_y,
            "is_start": True,
            "line_width": self.line_width,
            "pen_color": self.pen_color
        }
        socketio.emit("coordinate_update", data)
    
    def draw(self, event):
        """Continue drawing on mouse drag"""
        if not self.drawing:
            return
            
        x, y = event.x, event.y
        
        # Convert to normalized coordinates (0-1)
        norm_x = (x - self.x_offset) / self.image_width if self.image_width > 0 else 0
        norm_y = (y - self.y_offset) / self.image_height if self.image_height > 0 else 0
        
        # Bound coordinates to valid range
        norm_x = max(0, min(1, norm_x))
        norm_y = max(0, min(1, norm_y))
        
        # Draw a line segment
        if self.prev_x is not None and self.prev_y is not None:
            self.canvas.create_line(
                self.prev_x, self.prev_y, x, y, 
                fill=self.pen_color, width=self.line_width, tags="annotation"
            )
        
        # Draw endpoint
        self.canvas.create_oval(
            x - self.line_width / 2, y - self.line_width / 2,
            x + self.line_width / 2, y + self.line_width / 2,
            fill=self.pen_color, outline=self.pen_color, tags="annotation"
        )
        
        # Update previous point
        self.prev_x = x
        self.prev_y = y
        
        # Send to Flask server
        data = {
            "x": norm_x,
            "y": norm_y,
            "is_start": False,
            "line_width": self.line_width,
            "pen_color": self.pen_color
        }
        socketio.emit("coordinate_update", data)
    
    def stop_draw(self, event):
        """Stop drawing on mouse release"""
        self.drawing = False
        self.prev_x = None
        self.prev_y = None
    
    def upload_pdf(self):
        """Upload and display a PDF document."""
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        try:
            # Open the PDF file
            self.pdf_document = fitz.open(file_path)
            self.total_pages = len(self.pdf_document)
            self.current_page = 0
            
            # Update page counter
            self.page_var.set(1)  # Display is 1-based
            self.total_pages_var.set(f"/ {self.total_pages}")
            
            # Read PDF to memory buffer for sending
            with open(file_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # Send PDF to ALL connected clients (not just approved ones)
            # Students should see PDFs even in view-only mode
            print(f"Emitting new_pdf event to all clients: {self.total_pages} pages")
            socketio.emit("new_pdf", {
                "pdf_data": pdf_base64,
                "total_pages": self.total_pages,
                "current_page": self.current_page
            })
            print("new_pdf event emitted successfully")
            
            # Display first page
            self.render_pdf_page(self.current_page)
            
            print(f"PDF uploaded: {file_path}, {self.total_pages} pages")
        except Exception as e:
            print(f"Error uploading PDF: {e}")
    
    def render_pdf_page(self, page_num):
        """Render a specific PDF page to the canvas."""
        if not self.pdf_document or page_num < 0 or page_num >= self.total_pages:
            return
        
        try:
            # Get the page
            page = self.pdf_document[page_num]
            
            # Convert to an image with higher resolution for clarity
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Preserve original dimensions for proper mapping
            original_width, original_height = img.size
            
            # Calculate aspect ratio
            aspect_ratio = original_width / original_height
            canvas_aspect = self.canvas_width / self.canvas_height
            
            # Resize while preserving aspect ratio
            if aspect_ratio > canvas_aspect:
                # Image is wider than canvas (relative to height)
                new_width = self.canvas_width
                new_height = int(new_width / aspect_ratio)
            else:
                # Image is taller than canvas (relative to width)
                new_height = self.canvas_height
                new_width = int(new_height * aspect_ratio)
            
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Calculate offsets for centering
            self.image_width = new_width
            self.image_height = new_height
            self.x_offset = (self.canvas_width - new_width) // 2
            self.y_offset = (self.canvas_height - new_height) // 2
            
            # Display image
            self.current_image = img_resized
            self.current_image_tk = ImageTk.PhotoImage(img_resized)
            self.canvas.delete("all")  # Clear the canvas
            self.canvas.create_image(
                self.x_offset, self.y_offset, anchor="nw", image=self.current_image_tk
            )
            
            # Send page change to ALL clients (view-only students should see page changes)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            print(f"Emitting change_page event: page {page_num+1}/{self.total_pages}")
            socketio.emit("change_page", {
                "page_image": img_base64,
                "page_number": page_num,
                "canvas_width": original_width,
                "canvas_height": original_height
            })
            print("change_page event emitted successfully")
            
            print(f"Displayed PDF page {page_num+1}/{self.total_pages}")
        except Exception as e:
            print(f"Error rendering PDF page: {e}")
    
    def next_page(self):
        """Display the next page of the PDF."""
        if self.pdf_document and self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.page_var.set(self.current_page + 1)  # Display is 1-based
            self.render_pdf_page(self.current_page)
    
    def previous_page(self):
        """Display the previous page of the PDF."""
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.page_var.set(self.current_page + 1)  # Display is 1-based
            self.render_pdf_page(self.current_page)

    def clear_annotations(self):
        """Clear only annotations while keeping the image."""
        self.canvas.delete("annotation")
        self.prev_x = None
        self.prev_y = None
        # Notify clients to clear their views
        socketio.emit("clear_annotations")
    
    def clear_all(self):
        """Clear everything from the canvas"""
        self.canvas.delete("all")
        self.current_image_tk = None
        self.prev_x = None
        self.prev_y = None
        # Close PDF if open
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None
            self.total_pages = 0
            self.current_page = 0
            self.page_var.set(1)
            self.total_pages_var.set("/ 0")
        socketio.emit("clear_all")
    
    def draw_point(self, x, y, is_start, line_width, pen_color):
        """Draw a point or line segment from received data."""
        # Convert normalized coordinates (0-1) to canvas coordinates
        canvas_x = x * self.image_width + self.x_offset
        canvas_y = y * self.image_height + self.y_offset
        
        # Handle starting points
        if is_start:
            self.prev_x = None
            self.prev_y = None

        # Draw line if we have a previous point
        if self.prev_x is not None and self.prev_y is not None:
            self.canvas.create_line(
                self.prev_x, self.prev_y, canvas_x, canvas_y, 
                fill=pen_color, width=line_width, tags="annotation"
            )
        
        # Draw the current point
        self.canvas.create_oval(
            canvas_x - line_width / 2, canvas_y - line_width / 2,
            canvas_x + line_width / 2, canvas_y + line_width / 2,
            fill=pen_color, outline=pen_color, tags="annotation"
        )
        
        # Update previous point
        self.prev_x = canvas_x
        self.prev_y = canvas_y

    def process_coordinates(self):
        """Process coordinates from the queue."""
        while not coordinates_queue.empty():
            data = coordinates_queue.get()
            # Coordinates are already normalized (0-1)
            x = data["x"] 
            y = data["y"]
            is_start = data.get("is_start", False)
            line_width = data.get("line_width", self.line_width)
            pen_color = data.get("pen_color", self.pen_color)
            self.draw_point(x, y, is_start, line_width, pen_color)
        self.root.after(50, self.process_coordinates)
    
    def cleanup(self):
        """Clean up all resources when closing"""
        if self.voice_chat:
            self.voice_chat.cleanup()
        if self.pdf_document:
            self.pdf_document.close()

def run_tkinter(host_ip):
    """Start the Tkinter GUI."""
    root = Tk()
    root.geometry("1200x700")
    whiteboard_app = CollaborativeWhiteboard(root, host_ip)
    
    # Handle cleanup when window is closed
    def on_closing():
        whiteboard_app.cleanup()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()