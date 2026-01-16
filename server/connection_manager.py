import time
from tkinter import Frame, Label, Listbox, Button, MULTIPLE, StringVar, BooleanVar, RIGHT, LEFT, BOTH, Y
from tkinter import ttk
from server import connection_requests, connected_clients, socketio

class ConnectionRequestPanel:
    def __init__(self, parent):
        """Initialize the connection request panel."""
        self.parent = parent
        self.frame = Frame(parent, bg="#f0f0f0")
        self.frame.pack(fill="both", expand=True, padx=5, pady=10)

        # Heading
        header_frame = Frame(self.frame, bg="#f0f0f0")
        header_frame.pack(fill="x", pady=5)
        
        Label(header_frame, text="Connection Requests", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(side="left")
        
        # Auto-approve toggle
        self.auto_approve_var = BooleanVar(value=False) # Default to False for manual control
        ttk.Checkbutton(header_frame, text="Auto-Approve", variable=self.auto_approve_var).pack(side="right", padx=5)

        # Status label
        self.status_var = StringVar()
        self.status_var.set("No pending requests")
        self.status_label = Label(self.frame, textvariable=self.status_var, bg="#f0f0f0")
        self.status_label.pack(pady=5)

        # Request list frame with scrollbar
        list_frame = Frame(self.frame)
        list_frame.pack(fill=BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Request listbox
        self.request_list = Listbox(list_frame, selectmode=MULTIPLE, height=8, width=25)
        self.request_list.pack(side=LEFT, fill=BOTH, expand=True)

        # Configure scrollbar
        self.request_list.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.request_list.yview)

        # Bind selection event to show question
        self.request_list.bind("<<ListboxSelect>>", self.display_selected_question)

        # Label to show selected question
        self.question_label = Label(self.frame, text="Question: ", font=("Arial", 10), bg="#f8f8f8", wraplength=500, justify="left")
        self.question_label.pack(fill="x", padx=5, pady=5)

        # Buttons
        button_frame = Frame(self.frame, bg="#f0f0f0")
        button_frame.pack(fill="x", pady=5)

        ttk.Button(button_frame, text="Approve Selected", command=self.approve_selected).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Reject Selected", command=self.reject_selected).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_requests).pack(side="left", padx=2)

        # Request storage
        self.pending_requests = []  # List of request dictionaries

        # Automatically refresh requests on creation
        self.refresh_requests()

    def refresh_requests(self):
        """Refresh the list of connection requests."""
        current_time = time.time()
        
        # 1. Filter out stale requests (older than 2 minutes)
        valid_requests = []
        for request_data in self.pending_requests:
            if current_time - request_data["timestamp"] <= 120:
                valid_requests.append(request_data)
            else:
                # Disconnect stale
                client_id = request_data["client_id"]
                try:
                    socketio.server.disconnect(client_id)
                    print(f"Disconnected stale client request: {client_id}")
                except Exception as e:
                    print(f"Error disconnecting stale: {e}")
        
        self.pending_requests = valid_requests

        # 2. Add new requests from queue to the LIST
        while not connection_requests.empty():
            request = connection_requests.get()
            client_id = request["client_id"]
            
            if client_id not in connected_clients:
                # Check for auto-approval
                if self.auto_approve_var.get():
                    client_ip = request["client_ip"]
                    connected_clients.add(client_id)
                    socketio.emit("allow_student", {"allowed_sid": client_id})
                    socketio.emit("connection_approved", room=client_id)
                    print(f"Auto-approved connection from {client_ip} (ID: {client_id})")
                else:
                    # Append to list - No overwriting!
                    self.pending_requests.append(request)

        # 3. Save selection (by client_id)
        selected_client_ids = set()
        try:
            for idx in self.request_list.curselection():
                # For list, index in listbox == index in list
                if idx < len(self.pending_requests):
                     cid = self.pending_requests[idx]["client_id"]
                     selected_client_ids.add(cid)
        except Exception as e:
            print(f"Error saving selection: {e}")

        # 4. Update Listbox
        self.request_list.delete(0, "end")
        
        for idx, request_data in enumerate(self.pending_requests):
            client_ip = request_data["client_ip"]
            timestamp = time.strftime("%H:%M:%S", time.localtime(request_data["timestamp"]))
            question = request_data.get("question", "").strip()
            preview = (question[:30] + "...") if len(question) > 30 else question
            self.request_list.insert(idx, f"{client_ip} ({timestamp}) - {preview}")
            
            # Restore selection
            if request_data["client_id"] in selected_client_ids:
                self.request_list.selection_set(idx)

        # Update status
        if self.pending_requests:
            self.status_var.set(f"{len(self.pending_requests)} pending request(s)")
        else:
            self.status_var.set("No pending requests")

    def approve_selected(self):
        """Approve selected connection requests."""
        # Get selected INDICES from listbox
        selected_indexes = list(self.request_list.curselection())
        selected_indexes.sort(reverse=True) # Process reverse order to avoid index shifting issues if modifying inline
        
        # We need to collect IDs first because removing items shifts indices
        requests_to_approve = []
        for idx in selected_indexes:
            if idx < len(self.pending_requests):
                requests_to_approve.append(self.pending_requests[idx])
        
        for request_data in requests_to_approve:
            client_id = request_data["client_id"]
            client_ip = request_data["client_ip"]
            
            connected_clients.add(client_id)
            socketio.emit("allow_student", {"allowed_sid": client_id})
            socketio.emit("connection_approved", room=client_id)
            
            print(f"Approved connection from {client_ip} (ID: {client_id})")
            
            # Remove from pending list
            if request_data in self.pending_requests:
                self.pending_requests.remove(request_data)

        self.refresh_requests()

    def reject_selected(self):
        """Reject selected connection requests."""
        selected_indexes = list(self.request_list.curselection())
        selected_indexes.sort(reverse=True)
        
        requests_to_reject = []
        for idx in selected_indexes:
            if idx < len(self.pending_requests):
                requests_to_reject.append(self.pending_requests[idx])
        
        for request_data in requests_to_reject:
            client_id = request_data["client_id"]
            client_ip = request_data["client_ip"]
            
            socketio.emit("connection_rejected", room=client_id)
            try:
                socketio.server.disconnect(client_id)
            except Exception as e:
                print(f"Error disconnecting client {client_id}: {e}")
            print(f"Rejected connection from {client_ip} (ID: {client_id})")

            # Remove from pending list
            if request_data in self.pending_requests:
                self.pending_requests.remove(request_data)

        self.refresh_requests()

    def display_selected_question(self, event):
        """Show the full question of the selected request."""
        selection = self.request_list.curselection()
        if not selection:
            self.question_label.config(text="Question: ")
            return

        idx = selection[0]
        if idx < len(self.pending_requests):
            request_data = self.pending_requests[idx]
            question = request_data.get("question", "").strip()
            self.question_label.config(text=f"Question: {question or 'N/A'}")
        else:
            self.question_label.config(text="Question: ")


class ConnectedClientPanel:
    def __init__(self, parent):
        """Initialize the connected client panel."""
        self.parent = parent
        self.frame = Frame(parent, bg="#f0f0f0")
        self.frame.pack(fill="both", expand=True, padx=5, pady=10)

        # Heading
        header_frame = Frame(self.frame, bg="#f0f0f0")
        header_frame.pack(fill="x", pady=5)
        Label(header_frame, text="Active Students", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(side="left")

        # Status label
        self.status_var = StringVar()
        self.status_var.set("Connected: 0")
        Label(header_frame, textvariable=self.status_var, bg="#f0f0f0").pack(side="right", padx=10)

        # List frame
        list_frame = Frame(self.frame)
        list_frame.pack(fill=BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Listbox
        self.client_list = Listbox(list_frame, selectmode=MULTIPLE, height=6, width=25)
        self.client_list.pack(side=LEFT, fill=BOTH, expand=True)
        self.client_list.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.client_list.yview)

        # Buttons
        btn_frame = Frame(self.frame, bg="#f0f0f0")
        btn_frame.pack(fill="x", pady=5)

        ttk.Button(btn_frame, text="Disconnect Selected", command=self.disconnect_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh List", command=self.refresh_list).pack(side="left", padx=2)

        # Store IDs
        self.index_to_sid = {} # {index: sid}

        # Auto-refresh
        self.refresh_list()

    def refresh_list(self):
        """Refresh the list of connected clients."""
        # Save selection
        selected_sids = set()
        try:
            for idx in self.client_list.curselection():
                sid = self.index_to_sid.get(idx)
                if sid: selected_sids.add(sid)
        except: pass

        self.client_list.delete(0, "end")
        self.index_to_sid.clear()

        # connected_clients is a SET of SIDs. 
        # We don't have IPs easily available unless we store them. 
        # For now, display SID. (Improvement: Store IP map in server.py)
        
        for idx, sid in enumerate(list(connected_clients)):
            self.client_list.insert(idx, f"Student ID: {sid[:6]}...") # Show short ID
            self.index_to_sid[idx] = sid
            
            if sid in selected_sids:
                self.client_list.selection_set(idx)

        self.status_var.set(f"Connected: {len(connected_clients)}")
        
        # Schedule next refresh
        self.frame.after(3000, self.refresh_list)

    def disconnect_selected(self):
        """Disconnect selected clients."""
        selected_indexes = self.client_list.curselection()
        if not selected_indexes: return

        for idx in selected_indexes:
            sid = self.index_to_sid.get(idx)
            if sid:
                print(f"Force disconnecting student: {sid}")
                try:
                    # Notify client first
                    socketio.emit("force_disconnect", room=sid) 
                    socketio.server.disconnect(sid)
                except Exception as e:
                    print(f"Error disconnecting {sid}: {e}")
                
                if sid in connected_clients:
                    connected_clients.remove(sid)
        
        self.refresh_list()

