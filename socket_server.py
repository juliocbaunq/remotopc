import asyncio
import websockets
import json
import pyautogui
import base64
from io import BytesIO
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Initialize Firebase if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate('serviciofirebase.json')
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Configuración de PyAutoGUI
pyautogui.FAILSAFE = True

class RemoteDesktopServer:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = set()

    async def register(self, websocket):
        self.clients.add(websocket)
        try:
            await self.update_connection_status(True)
        except Exception as e:
            print(f"Error updating connection status: {e}")

    async def unregister(self, websocket):
        self.clients.remove(websocket)
        try:
            await self.update_connection_status(False)
        except Exception as e:
            print(f"Error updating connection status: {e}")

    async def update_connection_status(self, is_connected):
        # Actualizar estado en Firestore
        doc_ref = db.collection('remote_connections').document('status')
        doc_ref.set({
            'connected': is_connected,
            'last_updated': datetime.now(),
            'client_count': len(self.clients)
        }, merge=True)

    async def handle_command(self, websocket, command):
        try:
            data = json.loads(command)
            action = data.get('action')

            if action == 'mouse_move':
                x, y = data.get('x'), data.get('y')
                pyautogui.moveTo(x, y)
            elif action == 'mouse_click':
                button = data.get('button', 'left')
                pyautogui.click(button=button)
            elif action == 'key_press':
                key = data.get('key')
                pyautogui.press(key)
            elif action == 'get_screen':
                # Capturar pantalla
                screenshot = pyautogui.screenshot()
                # Convertir a base64
                buffered = BytesIO()
                screenshot.save(buffered, format="JPEG", quality=50)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                await websocket.send(json.dumps({
                    'type': 'screen',
                    'data': img_str
                }))

        except Exception as e:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handler(self, websocket, path):
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_command(websocket, message)
        finally:
            await self.unregister(websocket)

    async def start(self):
        server = await websockets.serve(self.handler, self.host, self.port)
        print(f"Server running on ws://{self.host}:{self.port}")
        await server.wait_closed()

def main():
    server = RemoteDesktopServer()
    asyncio.get_event_loop().run_until_complete(server.start())
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
