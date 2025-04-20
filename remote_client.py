import asyncio
import websockets
import json
import base64
from PIL import Image
import io
import tkinter as tk
from tkinter import ttk
import threading

class RemoteDesktopClient:
    def __init__(self, uri="ws://localhost:8765"):
        self.uri = uri
        self.websocket = None
        self.running = False
        self.setup_gui()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Remote Desktop Client")
        
        # Frame principal
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Canvas para mostrar la pantalla remota
        self.canvas = tk.Canvas(self.main_frame, width=800, height=600)
        self.canvas.grid(row=0, column=0, columnspan=2)
        
        # Botones de control
        ttk.Button(self.main_frame, text="Connect", command=self.start_connection).grid(row=1, column=0)
        ttk.Button(self.main_frame, text="Disconnect", command=self.stop_connection).grid(row=1, column=1)
        
        # Eventos del mouse
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Button-1>", self.on_mouse_click)
        
        # Estado de conexión
        self.status_label = ttk.Label(self.main_frame, text="Disconnected")
        self.status_label.grid(row=2, column=0, columnspan=2)

    def start_connection(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.run_async_loop, daemon=True).start()
            self.status_label.config(text="Connected")

    def stop_connection(self):
        self.running = False
        self.status_label.config(text="Disconnected")

    def run_async_loop(self):
        asyncio.run(self.connect())

    async def connect(self):
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                while self.running:
                    # Solicitar captura de pantalla
                    await websocket.send(json.dumps({
                        'action': 'get_screen'
                    }))
                    
                    # Recibir respuesta
                    response = await websocket.recv()
                    data = json.loads(response)
                    
                    if data['type'] == 'screen':
                        # Decodificar y mostrar la imagen
                        img_data = base64.b64decode(data['data'])
                        image = Image.open(io.BytesIO(img_data))
                        # Actualizar el canvas
                        self.update_canvas(image)
                    
                    # Pequeña pausa para no saturar
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Connection error: {e}")
            self.status_label.config(text=f"Error: {str(e)}")
        finally:
            self.websocket = None

    def update_canvas(self, image):
        # Redimensionar imagen si es necesario
        image = image.resize((800, 600), Image.Resampling.LANCZOS)
        self.photo = tk.PhotoImage(data=image.tobytes())
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

    async def send_command(self, command):
        if self.websocket:
            await self.websocket.send(json.dumps(command))

    def on_mouse_move(self, event):
        if self.websocket:
            asyncio.run(self.send_command({
                'action': 'mouse_move',
                'x': event.x,
                'y': event.y
            }))

    def on_mouse_click(self, event):
        if self.websocket:
            asyncio.run(self.send_command({
                'action': 'mouse_click',
                'button': 'left'
            }))

    def run(self):
        self.root.mainloop()

def main():
    client = RemoteDesktopClient()
    client.run()

if __name__ == "__main__":
    main()
