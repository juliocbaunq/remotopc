import asyncio
import aiohttp
import json
import uuid
import argparse
from aiohttp import web
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

class TunnelClient:
    def __init__(self, tunnel_server, local_port, tunnel_id=None):
        self.tunnel_server = tunnel_server
        self.local_port = local_port
        self.tunnel_id = tunnel_id or str(uuid.uuid4())
        self.session = None
        self.ws = None
        
        # Inicializar Firebase si no está inicializado
        if not firebase_admin._apps:
            cred = credentials.Certificate('serviciofirebase.json')
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    async def connect_to_tunnel(self):
        """Conectar al servidor de túnel"""
        self.session = aiohttp.ClientSession()
        ws_url = f"ws://{self.tunnel_server}/ws/tunnel/{self.tunnel_id}"
        
        try:
            self.ws = await self.session.ws_connect(ws_url)
            print(f"Connected to tunnel server. Your public URL is: http://{self.tunnel_server}/tunnel/{self.tunnel_id}")
            
            # Registrar en Firebase
            doc_ref = self.db.collection('tunnel_clients').document(self.tunnel_id)
            doc_ref.set({
                'tunnel_id': self.tunnel_id,
                'local_port': self.local_port,
                'server': self.tunnel_server,
                'connected_at': datetime.now(),
                'status': 'connected'
            })
            
            return True
        except Exception as e:
            print(f"Failed to connect to tunnel server: {e}")
            return False

    async def forward_request(self, request_data):
        """Reenviar petición al servidor local"""
        try:
            async with aiohttp.ClientSession() as session:
                method = request_data['method']
                path = request_data.get('path', '/')
                url = f"http://localhost:{self.local_port}{path}"
                
                # Preparar la petición
                kwargs = {
                    'headers': request_data.get('headers', {}),
                    'params': request_data.get('query', {})
                }
                
                if 'body' in request_data:
                    kwargs['data'] = request_data['body']
                
                # Hacer la petición al servidor local
                async with session.request(method, url, **kwargs) as response:
                    return {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'body': await response.text()
                    }
        except Exception as e:
            return {
                'status': 500,
                'headers': {'Content-Type': 'text/plain'},
                'body': f"Error forwarding request: {str(e)}"
            }

    async def handle_messages(self):
        """Manejar mensajes del servidor de túnel"""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    
                    if data['type'] == 'http_request':
                        # Procesar petición HTTP
                        response = await self.forward_request(data['data'])
                        await self.ws.send_str(json.dumps({
                            'type': 'http_response',
                            **response
                        }))
                    
                    elif data['type'] == 'request':
                        # Procesar otras peticiones
                        client_id = data['client_id']
                        await self.ws.send_str(json.dumps({
                            'type': 'response',
                            'client_id': client_id,
                            'data': {'status': 'ok'}
                        }))
                
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        except Exception as e:
            print(f"Error in message handling: {e}")
        finally:
            # Actualizar estado en Firebase
            doc_ref = self.db.collection('tunnel_clients').document(self.tunnel_id)
            doc_ref.update({
                'status': 'disconnected',
                'disconnected_at': datetime.now()
            })

    async def start(self):
        """Iniciar el cliente del túnel"""
        if await self.connect_to_tunnel():
            try:
                await self.handle_messages()
            finally:
                if self.session:
                    await self.session.close()

def main():
    parser = argparse.ArgumentParser(description='Tunnel Client')
    parser.add_argument('--server', default='localhost:8080', help='Tunnel server address')
    parser.add_argument('--port', type=int, required=True, help='Local port to tunnel')
    parser.add_argument('--id', help='Tunnel ID (optional)')
    
    args = parser.parse_args()
    
    client = TunnelClient(args.server, args.port, args.id)
    asyncio.get_event_loop().run_until_complete(client.start())

if __name__ == '__main__':
    main()
