from Py4GWCoreLib import *
import socket
import threading

module_name = "TCP Client"
client = None
client_thread = None


class TCPClient:
    def __init__(self, host='127.0.0.1', port=12345, buffer_size=4096):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.client_socket = None
        self.retry_timer = Timer()
        self.retry_timer.Start()
        self.connected = False
        self.running = False
        self.lock = threading.Lock()

    def connect_to_server(self):
        """Attempt to connect to the server using retry logic."""
        if not self.connected and self.retry_timer.HasElapsed(500):  # Retry every 500ms
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(1)  # Set a timeout for connection attempts
                self.client_socket.connect((self.host, self.port))
                self.connected = True
                self.running = True
                PySystem.Console.Log(module_name, f"Connected to server at {self.host}:{self.port}", PySystem.Console.MessageType.Success)
            except socket.error as e:
                PySystem.Console.Log(module_name, f"Error connecting to server: {e}", PySystem.Console.MessageType.Warning)
            finally:
                self.retry_timer.Reset()

    def send_message(self, message):
        """Send a message to the server."""
        if self.client_socket and self.connected:
            try:
                self.client_socket.sendall(message.encode())
                PySystem.Console.Log(module_name, f"Sent: {message}", PySystem.Console.MessageType.Info)
            except socket.error as e:
                PySystem.Console.Log(module_name, f"Error sending message: {e}", PySystem.Console.MessageType.Error)
                self.cleanup()

    def receive_messages(self):
        """Receive messages from the server in a loop."""
        while self.running:
            with self.lock:
                if self.client_socket and self.connected:
                    try:
                        data = self.client_socket.recv(self.buffer_size)
                        if data:
                            message = data.decode()
                            PySystem.Console.Log(module_name, f"Received: {message}", PySystem.Console.MessageType.Info)
                        else:
                            PySystem.Console.Log(module_name, "Server disconnected.", PySystem.Console.MessageType.Warning)
                            self.cleanup()
                            break
                    except socket.error as e:
                        PySystem.Console.Log(module_name, f"Error receiving message: {e}", PySystem.Console.MessageType.Error)
                        self.cleanup()
                        break

    def cleanup(self):
        """Clean up the client connection."""
        with self.lock:
            if self.client_socket:
                try:
                    self.client_socket.close()
                    PySystem.Console.Log(module_name, "Client socket closed.", PySystem.Console.MessageType.Info)
                except socket.error as e:
                    PySystem.Console.Log(module_name, f"Error closing client socket: {e}", PySystem.Console.MessageType.Warning)
                finally:
                    self.client_socket = None
                    self.connected = False
                    self.running = False


# Client Thread Function
def client_thread_function():
    global client
    try:
        while client.running:
            try:
                client.client_socket.settimeout(0.5)  # Ensure recv() times out
                client.receive_messages()
            except socket.timeout:
                continue  # Timeout allows us to check the running flag
            except Exception as e:
                if client.running:  # Only log errors if the client is supposed to be running
                    PySystem.Console.Log(module_name, f"Client thread error: {e}", PySystem.Console.MessageType.Warning)
    except Exception as e:
        PySystem.Console.Log(module_name, f"Unexpected client thread error: {e}", PySystem.Console.MessageType.Error)
    finally:
        PySystem.Console.Log(module_name, "Client thread exiting.", PySystem.Console.MessageType.Info)



# Utility Functions for Embedded Use
def initialize_client():
    """Initialize the TCP client and start the receiving thread."""
    global client, client_thread
    if client is None:
        client = TCPClient()

    if client_thread is None or not client_thread.is_alive():
        client.connect_to_server()
        if client.connected:
            client_thread = threading.Thread(target=client_thread_function, daemon=True)
            client_thread.start()
            PySystem.Console.Log(module_name, "Client thread started.", PySystem.Console.MessageType.Info)


def stop_client():
    """Stop the TCP client and its thread."""
    global client, client_thread
    if client:
        client.running = False
        # Closing client socket interrupts recv()
        try:
            if client.client_socket:
                client.client_socket.close()
                PySystem.Console.Log(module_name, "Client socket closed.", PySystem.Console.MessageType.Info)
        except Exception as e:
            PySystem.Console.Log(module_name, f"Error closing client socket: {e}", PySystem.Console.MessageType.Warning)
        client.cleanup()
        client = None

    if client_thread and client_thread.is_alive():
        client_thread.join(timeout=2)  # Wait for the thread to exit
        if client_thread.is_alive():
            PySystem.Console.Log(module_name, "Forcefully terminating client thread.", PySystem.Console.MessageType.Warning)
            client_thread = None  # Allow the program to proceed regardless


# GUI Rendering Function
def DrawWindow():
    global module_name, client
    try:
        if PyImGui.begin(module_name):
            PyImGui.text("TCP Client")
            PyImGui.separator()

            if client is None or not client.connected:
                if PyImGui.button("Connect to Server"):
                    initialize_client()
                    PySystem.Console.Log(module_name, "Client initialized.", PySystem.Console.MessageType.Info)
            else:
                if client.connected:
                    PyImGui.text("Connected to server.")
                    if PyImGui.button("Disconnect"):
                        stop_client()
                        PySystem.Console.Log(module_name, "Client disconnected.", PySystem.Console.MessageType.Info)

            PyImGui.end()
    except Exception as e:
        PySystem.Console.Log(module_name, f"Error in DrawWindow: {str(e)}", PySystem.Console.MessageType.Error)
        raise


# Main Loop
def main():
    try:
        DrawWindow()
    except Exception as e:
        PySystem.Console.Log(module_name, f"Unexpected error: {str(e)}", PySystem.Console.MessageType.Error)
