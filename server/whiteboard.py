from tkinter import Tk, Canvas, Button, filedialog, ttk, Frame, Label, StringVar, Scale, HORIZONTAL, IntVar, Entry
import time
import threading
import io
from PIL import Image, ImageTk
import base64
import fitz  # PyMuPDF for PDF handling

from voice_chat import VoiceChat
from connection_manager import ConnectionRequestPanel, ConnectedClientPanel
from server import socketio, coordinates_queue, connected_clients

# Global reference for connection_manager to access voice_chat
whiteboard_instance = None

class CollaborativeWhiteboard:
    def __init__(self, root, host_ip):
        self.root = root
        self.root.title("Collaborative Whiteboard with Voice Chat")
        self.host_ip = host_ip
        
        # Detect screen size for responsive layout
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Calculate responsive sidebar width (12% of screen width, min 260, max 320)
        sidebar_width = max(260, min(320, int(screen_width * 0.12)))
        
        # Main frame
        self.main_frame = Frame(root)
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=5)
        
        # Create left panel for tools and controls (responsive width)
        self.left_panel_container = Frame(self.main_frame, width=sidebar_width, bg="#f0f0f0")
        self.left_panel_container.pack(side="left", fill="y", padx=5, pady=5)
        self.left_panel_container.pack_propagate(False)  # Prevent shrinking
        
        # Setup Scrollbar for left panel (use responsive width)
        canvas_width = sidebar_width - 20  # Account for padding
        self.left_canvas = Canvas(self.left_panel_container, width=canvas_width, bg="#f0f0f0", highlightthickness=0)
        self.left_scrollbar = ttk.Scrollbar(self.left_panel_container, orient="vertical", command=self.left_canvas.yview)
        
        self.scrollable_frame = Frame(self.left_canvas, bg="#f0f0f0")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        )
        
        self.left_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            self.left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mouse wheel to canvas and all child widgets
        self.left_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        self.left_canvas.pack(side="left", fill="both", expand=True)
        self.left_scrollbar.pack(side="right", fill="y")
        
        # Use scrollable_frame as the parent for all controls
        self.left_panel = self.scrollable_frame
        
        # Create right panel for canvas (takes remaining space)
        self.right_panel = Frame(self.main_frame, bg="white")
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        # Canvas Setup - Make it fully responsive
        self.canvas = Canvas(self.right_panel, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Dynamic canvas dimensions (will be updated on window resize)
        self.canvas_width = 1280
        self.canvas_height = 720
        
        # Bind to window resize to update canvas and re-render PDF
        self.root.bind("<Configure>", self.on_window_resize)
        self.resize_pending = False
        
        # Initialize the voice chat
        self.voice_chat = VoiceChat(host_ip)
        
        # Create connection panel with modern styling
        self.connection_frame = Frame(self.left_panel, bg="white", relief="solid", borderwidth=1)
        self.connection_frame.pack(fill="x", padx=5, pady=(10,5))
        
        Label(self.connection_frame, text="📡 Server Info", font=("Arial", 11, "bold"), 
              bg="white", fg="#2c3e50").pack(pady=(8,4))
        
        # IP Display with better styling
        ip_frame = Frame(self.connection_frame, bg="white")
        ip_frame.pack(pady=4)
        Label(ip_frame, text="Server IP:", font=("Arial", 9), bg="white", fg="#7f8c8d").pack(side="left")
        Label(ip_frame, text=f" {host_ip}", font=("Arial", 9, "bold"), 
              bg="white", fg="#27ae60").pack(side="left")
        
        # Connection Buttons
        btn_frame = Frame(self.connection_frame, bg="#f0f0f0")
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Disconnect Voice", command=self.disconnect_voice).pack(side="left", padx=2)
        
        # Status display with better styling
        Label(self.connection_frame, textvariable=self.voice_chat.status_var,
              font=("Arial", 8), bg="white", fg="#7f8c8d").pack(pady=2)
        
        # Connected clients display
        self.clients_var = StringVar(value="Connected Clients: 0")
        Label(self.connection_frame, textvariable=self.clients_var, 
              font=("Arial", 9), bg="white", fg="#3498db").pack(pady=(2,8))
        
        
        # Add connection request panel
        self.connection_request_panel = ConnectionRequestPanel(self.left_panel)
        
        # Add connected clients panel (Active Students)
        self.connected_client_panel = ConnectedClientPanel(self.left_panel)
        
        # Drawing Tools with modern styling
        self.drawing_frame = Frame(self.left_panel, bg="white", relief="solid", borderwidth=1)
        self.drawing_frame.pack(fill="x", padx=5, pady=5)
        
        Label(self.drawing_frame, text="🎨 Drawing Tools", font=("Arial", 11, "bold"), 
              bg="white", fg="#2c3e50").pack(pady=(8,4))
        
        # Pen Colors with emoji labels
        Label(self.drawing_frame, text="Pen Color:", font=("Arial", 9), bg="white").pack(pady=(4,2))
        colors_frame = Frame(self.drawing_frame, bg="white")
        colors_frame.pack(pady=4)
        
        colors = [("⚫", "black"), ("🔴", "red"), ("🔵", "blue"), ("🟢", "green"), ("🟡", "yellow")]
        for emoji, col in colors:
            btn = Button(colors_frame, text=emoji, width=3, height=1,
                        command=lambda c=col: self.set_pen_color(c),
                        relief="raised", borderwidth=2)
            btn.pack(side="left", padx=2)
            
        # Line Width with better styling
        Label(self.drawing_frame, text="Line Thickness:", font=("Arial", 9), bg="white").pack(pady=(8,2))
        width_frame = Frame(self.drawing_frame, bg="white")
        width_frame.pack(fill="x", padx=8, pady=(0,8))
        Scale(width_frame, from_=1, to=10, orient=HORIZONTAL, 
              command=self.set_line_width, bg="white", showvalue=True).pack(fill="x")

        # Initialize drawing attributes
        self.pen_color = "blue"
        self.line_width = 3
        
        # PDF Controls with modern styling
        self.pdf_frame = Frame(self.left_panel, bg="white", relief="solid", borderwidth=1)
        self.pdf_frame.pack(fill="x", padx=5, pady=5)
        
        Label(self.pdf_frame, text="📄 PDF Controls", font=("Arial", 11, "bold"), 
              bg="white", fg="#2c3e50").pack(pady=(8,4))
        
        # PDF Navigation - Horizontal row with better styling
        nav_frame = Frame(self.pdf_frame, bg="white")
        nav_frame.pack(pady=8)
        
        self.page_var = IntVar(value=1)
        self.total_pages_var = StringVar(value="/ 0")
        
        ttk.Button(nav_frame, text="◀", width=3, command=self.previous_page).pack(side="left", padx=2)
        
        page_display = Frame(nav_frame, bg="white")
        page_display.pack(side="left", padx=8)
        Entry(page_display, textvariable=self.page_var, width=4, justify="center",
              font=("Arial", 10)).pack(side="left")
        Label(page_display, textvariable=self.total_pages_var, 
              font=("Arial", 10), bg="white").pack(side="left")
        
        ttk.Button(nav_frame, text="▶", width=3, command=self.next_page).pack(side="left", padx=2)
        
        # PDF Action Buttons - Better layout
        btn_container = Frame(self.pdf_frame, bg="white")
        btn_container.pack(pady=4, padx=4)
        
        ttk.Button(btn_container, text="📤 Upload PDF", command=self.upload_pdf).pack(side="left", padx=2)
        ttk.Button(btn_container, text="🗑️ Clear All", command=self.clear_all).pack(side="left", padx=2)
        
        Frame(self.pdf_frame, bg="white", height=8).pack()  # Bottom padding

        
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
        
        # Start the coordinate processing (reduced frequency for better performance)
        self.root.after(100, self.process_coordinates)
        # Start audio level update
        # Start connected clients counter update
        self.root.after(1000, self.update_client_count)
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
        self.root.after(1000, self.update_client_count)
    
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
        
        # Draw a line segment with smooth, rounded appearance
        if self.prev_x is not None and self.prev_y is not None:
            self.canvas.create_line(
                self.prev_x, self.prev_y, x, y, 
                fill=self.pen_color, width=self.line_width,
                capstyle="round", joinstyle="round",
                tags="annotation"
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
            
            # SAVE old dimensions BEFORE updating (for scaling annotations)
            old_image_width = getattr(self, 'image_width', new_width)
            old_image_height = getattr(self, 'image_height', new_height)  
            old_x_offset = getattr(self, 'x_offset', (self.canvas_width - new_width) // 2)
            old_y_offset = getattr(self, 'y_offset', (self.canvas_height - new_height) // 2)
            
            # NOW update to new dimensions
            self.image_width = new_width
            self.image_height = new_height
            self.x_offset = (self.canvas_width - new_width) // 2
            self.y_offset = (self.canvas_height - new_height) // 2
            
            # Track old dimensions for scaling annotations (REMOVED - now done above)
            # old_image_width = self.image_width if hasattr(self, 'image_width') else new_width
            # old_image_height = self.image_height if hasattr(self, 'image_height') else new_height
            # old_x_offset = self.x_offset if hasattr(self, 'x_offset') else self.x_offset
            # old_y_offset = self.y_offset if hasattr(self, 'y_offset') else self.y_offset
            
            # Display image
            self.current_image = img_resized
            self.current_image_tk = ImageTk.PhotoImage(img_resized)
            
            # Only delete the PDF background, preserve annotations
            self.canvas.delete("pdf_background")
            self.canvas.create_image(
                self.x_offset, self.y_offset, anchor="nw", image=self.current_image_tk, tags="pdf_background"
            )
            # Ensure background is behind all annotations
            self.canvas.tag_lower("pdf_background")
            
            # Scale existing annotations if dimensions changed
            if (old_image_width != new_width or old_image_height != new_height or 
                old_x_offset != self.x_offset or old_y_offset != self.y_offset):
                self.scale_annotations(old_image_width, old_image_height, old_x_offset, old_y_offset)
            
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
    
    def on_window_resize(self, event):
        """Handle window resize events to update canvas and re-render PDF."""
        # Only handle resize for the root window
        if event.widget != self.root:
            return
        
        # Cancel any pending resize refresh
        if self.resize_pending:
            self.root.after_cancel(self.resize_pending)
        
        # Schedule a refresh after resizing stops (longer debounce for smoother resize)
        self.resize_pending = self.root.after(300, self.refresh_canvas_size)
    
    def refresh_canvas_size(self):
        """Update canvas dimensions and re-render PDF if loaded."""
        self.resize_pending = False
        
        # Get actual canvas dimensions
        new_width = self.canvas.winfo_width()
        new_height = self.canvas.winfo_height()
        
        # Only update if dimensions are valid and have changed
        if new_width > 1 and new_height > 1:
            if new_width != self.canvas_width or new_height != self.canvas_height:
                self.canvas_width = new_width
                self.canvas_height = new_height
                
                # Re-render current PDF page if one is loaded
                if self.pdf_document and hasattr(self, 'current_page'):
                    self.render_pdf_page(self.current_page)
    
    def scale_annotations(self, old_width, old_height, old_x_offset, old_y_offset):
        """Scale all annotations proportionally when canvas size changes."""
        if old_width <= 0 or old_height <= 0:
            return
        
        # Prevent concurrent scaling operations
        if hasattr(self, '_scaling_in_progress') and self._scaling_in_progress:
            return
        
        self._scaling_in_progress = True
        
        try:
            # Calculate scale factors
            scale_x = self.image_width / old_width
            scale_y = self.image_height / old_height
            
            # Get all canvas items except the PDF background
            all_items = self.canvas.find_all()
            for item in all_items:
                tags = self.canvas.gettags(item)
                # Skip the PDF background
                if "pdf_background" in tags:
                    continue
                
                # Get item type
                item_type = self.canvas.type(item)
                
                if item_type == "line":
                    # Scale line coordinates
                    coords = self.canvas.coords(item)
                    new_coords = []
                    for i in range(0, len(coords), 2):
                        # Get original position relative to old PDF
                        rel_x = (coords[i] - old_x_offset) * scale_x
                        rel_y = (coords[i+1] - old_y_offset) * scale_y
                        # Apply new offset
                        new_x = rel_x + self.x_offset
                        new_y = rel_y + self.y_offset
                        new_coords.extend([new_x, new_y])
                    self.canvas.coords(item, *new_coords)
                    
                    # Also scale line width
                    old_width_val = self.canvas.itemcget(item, "width")
                    if old_width_val:
                        try:
                            new_width_val = float(old_width_val) * min(scale_x, scale_y)
                            self.canvas.itemconfig(item, width=new_width_val)
                        except:
                            pass
                
                elif item_type == "oval":
                    # Scale oval (endpoint dots) coordinates
                    coords = self.canvas.coords(item)
                    if len(coords) == 4:
                        x1, y1, x2, y2 = coords
                        # Get center
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        # Scale center position
                        rel_x = (center_x - old_x_offset) * scale_x
                        rel_y = (center_y - old_y_offset) * scale_y
                        new_center_x = rel_x + self.x_offset
                        new_center_y = rel_y + self.y_offset
                        # Scale radius
                        radius = (x2 - x1) / 2
                        new_radius = radius * min(scale_x, scale_y)
                        # Update coordinates
                        self.canvas.coords(item, 
                            new_center_x - new_radius, new_center_y - new_radius,
                            new_center_x + new_radius, new_center_y + new_radius)
        finally:
            self._scaling_in_progress = False


    
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
        processed_count = 0
        # Batch processing - limit to 20 coordinates per cycle for smooth UI
        while not coordinates_queue.empty() and processed_count < 20:
            data = coordinates_queue.get()
            processed_count += 1
            # Coordinates are already normalized (0-1)
            x = data["x"] 
            y = data["y"]
            is_start = data.get("is_start", False)
            line_width = data.get("line_width", self.line_width)
            pen_color = data.get("pen_color", self.pen_color)
            self.draw_point(x, y, is_start, line_width, pen_color)
        
        # Only update UI once per batch for better performance
        if processed_count > 0:
            self.canvas.update_idletasks()
        
        self.root.after(100, self.process_coordinates)
    
    def cleanup(self):
        """Clean up all resources when closing"""
        if self.voice_chat:
            self.voice_chat.cleanup()
        if self.pdf_document:
            self.pdf_document.close()

def run_tkinter(host_ip):
    """Start the Tkinter GUI."""
    global whiteboard_instance
    root = Tk()
    
    # Get screen dimensions for responsive sizing
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Set window size to 80% of screen size (better for different displays)
    window_width = int(screen_width * 0.8)
    window_height = int(screen_height * 0.8)
    
    # Center the window
    x_position = (screen_width - window_width) // 2
    y_position = (screen_height - window_height) // 2
    
    root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
    
    # Set minimum size (60% of screen or absolute minimum)
    min_width = max(1000, int(screen_width * 0.6))
    min_height = max(600, int(screen_height * 0.6))
    root.minsize(min_width, min_height)
    whiteboard_app = CollaborativeWhiteboard(root, host_ip)
    whiteboard_instance = whiteboard_app  # Set global reference
    
    # Handle cleanup when window is closed
    def on_closing():
        whiteboard_app.cleanup()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()