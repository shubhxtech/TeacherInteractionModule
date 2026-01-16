import socket
import pyaudio
import threading
import time
from tkinter import StringVar

# Audio settings
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 22050
VOICE_PORT = 8000

class VoiceChat:
    def __init__(self, host):
        self.host = host
        self.running = False  # Overall server running state
        self.client_connected = False # Specific client connection state
        self.stop_event = threading.Event()
        self.server_socket = None
        
        # Current active connection details
        self.connection = None
        self.client_address = None
        self.client_thread = None

        self.audio = None
        self.input_stream = None
        self.output_stream = None

        self.status_var = StringVar()
        self.status_var.set("Voice Chat: Disconnected")
        self.audio_level = 0
        
        # Lock for thread safety when swapping connections
        self.lock = threading.RLock()

    def initialize_audio(self):
        """Initialize PyAudio streams."""
        with self.lock:
            if self.audio is not None:
                return # Already initialized

            try:
                self.audio = pyaudio.PyAudio()
            except Exception as e:
                print(f"Failed to create PyAudio instance: {e}")
                self.status_var.set(f"Voice Chat: Audio Driver Error")
                return

            # Try Input Stream (Microphone)
            try:
                self.input_stream = self.audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
            except Exception as e:
                print(f"Warning: Failed to open microphone: {e}")
                self.input_stream = None

            # Try Output Stream (Speakers)
            try:
                self.output_stream = self.audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK
                )
            except Exception as e:
                print(f"Warning: Failed to open speakers: {e}")
                self.output_stream = None

            # Check if at least one stream works
            if self.input_stream is None and self.output_stream is None:
                print("Error: No audio devices available")
                self.status_var.set("Voice Chat: No Audio Devices")
                self.cleanup_audio()
            else:
                modes = []
                if self.input_stream: modes.append("Mic")
                if self.output_stream: modes.append("Speaker")
                print(f"Audio initialized. Modes: {', '.join(modes)}")

    def cleanup_audio(self):
        """Clean up PyAudio streams."""
        with self.lock:
            if self.input_stream:
                try:
                    self.input_stream.stop_stream()
                    self.input_stream.close()
                except: pass
                self.input_stream = None

            if self.output_stream:
                try:
                    self.output_stream.stop_stream()
                    self.output_stream.close()
                except: pass
                self.output_stream = None

            if self.audio:
                try:
                    self.audio.terminate()
                except: pass
                self.audio = None

    def start_server(self):
        """Start the voice server listener."""
        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.status_var.set("Voice Chat: Waiting for connection...")

        def server_listen_loop():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((self.host, VOICE_PORT))
                self.server_socket.listen(1)
                self.server_socket.settimeout(1.0)
                print(f"Voice server listening on {self.host}:{VOICE_PORT}")

                while not self.stop_event.is_set():
                    try:
                        # Accept new connection
                        conn, addr = self.server_socket.accept()
                        print(f"Voice connection request from {addr[0]}")
                        
                        # Handle the new client in a unified way (disconnecting old if exists)
                        self.handle_new_connection(conn, addr)
                        
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if not self.stop_event.is_set():
                            print(f"Error accepting voice connection: {e}")
                        
            except Exception as e:
                print(f"Voice server fatal error: {e}")
                self.status_var.set(f"Voice Chat: Error - {e}")
            finally:
                self.cleanup()

        # Start the listener thread
        server_thread_handle = threading.Thread(target=server_listen_loop)
        server_thread_handle.daemon = True
        server_thread_handle.start()

    def handle_new_connection(self, new_conn, addr):
        """Handle a new client connection, replacing any existing one."""
        with self.lock:
            # 1. Close existing connection if any
            if self.connection:
                print("Disconnecting previous client...")
                try:
                    self.client_connected = False # Signal threads to stop
                    self.connection.close() 
                except: pass
                self.connection = None
            
            # 2. Setup new connection
            self.connection = new_conn
            self.client_address = addr
            
            # 3. Initialize audio if needed
            self.initialize_audio()
            
            # 4. Start handler thread
            # 4. Start handler thread
            self.client_connected = True
            msg = f"Voice Chat: Connected to {addr[0]}"
            if self.audio is None:
                msg += " (No Audio Device)"
            self.status_var.set(msg)
            print(f"Voice Chat: Auto-accepted connection from {addr[0]}. Audio initialized: {self.audio is not None}")
            
            # Start a single thread to manage both send/receive for this client
            thread = threading.Thread(target=self.client_io_loop)
            thread.daemon = True
            thread.start()

    def client_io_loop(self):
        """Manage Audio I/O for the currently connected client."""
        # Start helper threads for simultaneous read/write
        send_thread = threading.Thread(target=self.send_audio)
        recv_thread = threading.Thread(target=self.receive_audio)
        
        send_thread.daemon = True
        recv_thread.daemon = True
        
        send_thread.start()
        recv_thread.start()
        
        # Wait for either to finish (meaning disconnect)
        send_thread.join()
        recv_thread.join()
        
        # When threads exit, cleanup this specific connection
        with self.lock:
            if self.client_connected: # If we are still "supposed" to be connected, it means an error occurred
                print(f"Client {self.client_address} disconnected.")
                self.client_connected = False
                self.status_var.set("Voice Chat: Waiting for connection...")
                # We do NOT cleanup audio here, to keep it ready for next client quickly
                # But we do close the socket
                if self.connection:
                    try:
                        self.connection.close()
                    except: pass
                    self.connection = None

    def send_audio(self):
        """Send microphone input to client."""
        packets_sent = 0
        try:
            while self.client_connected and self.input_stream:
                data = self.input_stream.read(CHUNK, exception_on_overflow=False)
                if len(data) > 0:
                    packets_sent += 1
                    if packets_sent % 100 == 0:
                        print(f"Sent {packets_sent} audio chunks")
                        
                    # Calculate level for UI
                    signal = [int.from_bytes(data[i:i+2], byteorder='little', signed=True) 
                              for i in range(0, len(data), 2)]
                    rms = sum(x*x for x in signal) / len(signal) if signal else 0
                    self.audio_level = min(100, int(rms / 100))

                    if self.connection:
                        self.connection.sendall(data)
                        
        except (ConnectionResetError, BrokenPipeError):
            print("Send: Client disconnected")
            self.client_connected = False
        except Exception as e:
            if self.client_connected:
                print(f"Send audio error: {e}")
                self.client_connected = False

    def receive_audio(self):
        """Receive audio from client and play it."""
        packets_received = 0
        try:
            while self.client_connected and self.connection and self.output_stream:
                data = self.connection.recv(CHUNK)
                if not data:
                    print("Receive: Client disconnected (EOF)")
                    self.client_connected = False
                    break
                
                packets_received += 1
                if packets_received % 100 == 0:
                    print(f"Received {packets_received} audio chunks")
                
                self.output_stream.write(data)
                
        except (ConnectionResetError, BrokenPipeError):
            print("Receive: Client disconnected")
            self.client_connected = False
        except Exception as e:
            if self.client_connected:
                print(f"Receive audio error: {e}")
                self.client_connected = False

    def cleanup(self):
        """Full cleanup of server resources."""
        self.running = False
        self.stop_event.set()
        self.client_connected = False
        
        with self.lock:
            if self.connection:
                try:
                    self.connection.close()
                except: pass
                self.connection = None

            if self.server_socket:
                try:
                    self.server_socket.close()
                except: pass
                self.server_socket = None

            self.cleanup_audio()
        print("Voice chat resources cleaned up")
