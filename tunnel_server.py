import asyncio
import aiohttp
from aiohttp import web
import json
import ssl
import base64
import os
from cryptography.fernet import Fernet
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

class TunnelServer:
    def __init__(self, port=8080):
        self.port = port
        self.clients = {}
        self.tunnels = {}
        self.key = Fernet.generate_key()
        self.cipher = Fernet(self.key)
        
        
        # Configurar logging
        import logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('TunnelServer')
        
        # Inicializar Firebase si no está inicializado
        if not firebase_admin._apps:
            self.port = port
        self.clients = {}
        self.tunnels = {}
        self.key = Fernet.generate_key()
        self.cipher = Fernet(self.key)
        
        # Configurar logging
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('TunnelServer')
        
        # Inicializar Firebase si no está inicializado
        if not firebase_admin._apps:
            cred = credentials.Certificate('serviciofirebase.json')
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    async def register_tunnel(self, tunnel_id, ws):
        """Registrar un nuevo túnel"""
        try:
            if tunnel_id not in self.tunnels:
                self.tunnels[tunnel_id] = {
                    'websocket': ws,
                    'created_at': datetime.now(),
                    'clients': set(),
                    'status': 'connected'
                }
                # Registrar en Firebase
                await self.update_tunnel_status(tunnel_id, True)
                self.logger.info(f'Túnel {tunnel_id} registrado exitosamente')
                return True
            else:
                self.logger.warning(f'Túnel {tunnel_id} ya existe')
                return False
        except Exception as e:
            self.logger.error(f'Error registrando túnel {tunnel_id}: {e}')
            return False

    async def unregister_tunnel(self, tunnel_id):
        """Eliminar un túnel"""
        if tunnel_id in self.tunnels:
            await self.update_tunnel_status(tunnel_id, False)
            del self.tunnels[tunnel_id]

    async def update_tunnel_status(self, tunnel_id, is_active):
        """Actualizar estado del túnel en Firebase"""
        try:
            # Obtener IP pública
            import requests
            public_ip = requests.get('https://api.ipify.org').text
            
            doc_ref = self.db.collection('tunnels').document(tunnel_id)
            doc_ref.set({
                'active': is_active,
                'last_updated': datetime.now(),
                'local_url': f'http://localhost:{self.port}/tunnel/{tunnel_id}',
                'public_url': f'http://{public_ip}:{self.port}/tunnel/{tunnel_id}',
                'public_ip': public_ip,
                'status': 'connected' if is_active else 'disconnected'
            }, merge=True)
            self.logger.info(f'Estado del túnel {tunnel_id} actualizado: {"activo" if is_active else "inactivo"}')
        except Exception as e:
            self.logger.error(f'Error actualizando estado del túnel {tunnel_id}: {e}')

    async def handle_tunnel_connection(self, request):
        """Manejar conexión WebSocket para el túnel"""
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        
        tunnel_id = request.match_info['tunnel_id']
        print(f"Nuevo intento de conexión de túnel: {tunnel_id}")
        
        if await self.register_tunnel(tunnel_id, ws):
            try:
                print(f"Túnel {tunnel_id} registrado exitosamente")
                async for msg in ws:
                    if msg.type == web.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            if 'type' in data:
                                if data['type'] == 'response':
                                    client_id = data.get('client_id')
                                    if client_id in self.clients:
                                        client_ws = self.clients[client_id]['websocket']
                                        await client_ws.send_str(json.dumps({
                                            'type': 'response',
                                            'data': data['data']
                                        }))
                        except Exception as e:
                            print(f"Error procesando mensaje del túnel {tunnel_id}: {e}")
                    elif msg.type == web.WSMsgType.ERROR:
                        print(f"Error en conexión de túnel {tunnel_id}: {ws.exception()}")
            finally:
                print(f"Túnel {tunnel_id} desconectado")
                await self.unregister_tunnel(tunnel_id)
        else:
            print(f"No se pudo registrar el túnel {tunnel_id}")
        return ws

    async def handle_client_connection(self, request):
        """Manejar conexión WebSocket para el cliente"""
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        
        client_id = base64.urlsafe_b64encode(os.urandom(16)).decode('ascii')
        tunnel_id = request.match_info['tunnel_id']
        
        print(f"Nueva conexión de cliente {client_id} para túnel {tunnel_id}")
        
        if tunnel_id in self.tunnels:
            self.clients[client_id] = {
                'websocket': ws,
                'tunnel_id': tunnel_id,
                'connected_at': datetime.now()
            }
            self.tunnels[tunnel_id]['clients'].add(client_id)
            print(f"Cliente {client_id} registrado para túnel {tunnel_id}")
            
            try:
                async for msg in ws:
                    if msg.type == web.WSMsgType.TEXT:
                        try:
                            if tunnel_id in self.tunnels:
                                tunnel_ws = self.tunnels[tunnel_id]['websocket']
                                data = json.loads(msg.data)
                                await tunnel_ws.send_str(json.dumps({
                                    'type': 'request',
                                    'client_id': client_id,
                                    'data': data
                                }))
                            else:
                                print(f"Túnel {tunnel_id} no encontrado para cliente {client_id}")
                                break
                        except Exception as e:
                            print(f"Error procesando mensaje del cliente {client_id}: {e}")
                    elif msg.type == web.WSMsgType.ERROR:
                        print(f"Error en conexión de cliente {client_id}: {ws.exception()}")
            finally:
                print(f"Cliente {client_id} desconectado del túnel {tunnel_id}")
                if client_id in self.clients:
                    del self.clients[client_id]
                if tunnel_id in self.tunnels and client_id in self.tunnels[tunnel_id]['clients']:
                    self.tunnels[tunnel_id]['clients'].remove(client_id)
        else:
            print(f"Túnel {tunnel_id} no encontrado para cliente {client_id}")
        return ws

    async def handle_http_request(self, request):
        """Manejar peticiones HTTP normales"""
        tunnel_id = request.match_info['tunnel_id']
        if tunnel_id not in self.tunnels:
            return web.Response(text='Tunnel not found', status=404)
        
        # Crear payload
        payload = {
            'method': request.method,
            'path': request.path,
            'headers': dict(request.headers),
            'query': dict(request.query)
        }
        
        if request.body_exists:
            payload['body'] = await request.text()
        
        # Enviar al túnel
        tunnel_ws = self.tunnels[tunnel_id]['websocket']
        await tunnel_ws.send_str(json.dumps({
            'type': 'http_request',
            'data': payload
        }))
        
        # Esperar respuesta
        async for msg in tunnel_ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data['type'] == 'http_response':
                    return web.Response(
                        text=data['body'],
                        status=data['status'],
                        headers=data['headers']
                    )
        
        return web.Response(text='Tunnel error', status=500)

    async def init_app(self):
        """Inicializar la aplicación web"""
        app = web.Application()
        
        # Configurar CORS middleware
        app.router.add_get('/ws/tunnel/{tunnel_id}', self.handle_tunnel_connection)
        app.router.add_get('/ws/client/{tunnel_id}', self.handle_client_connection)
        app.router.add_route('*', '/tunnel/{tunnel_id}/{tail:.*}', self.handle_http_request)
        app.router.add_route('OPTIONS', '/{tail:.*}', self.handle_options)
        
        # Agregar middleware para CORS
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = '*'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        app.middlewares.append(cors_middleware)
        return app

    def run(self):
        """Iniciar el servidor"""
        async def start_server():
            app = await self.init_app()
            runner = web.AppRunner(app)
            await runner.setup()
            
            # Escuchar en todas las interfaces (0.0.0.0)
            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()
            
            print(f"Tunnel server running on port {self.port}")
            print(f"Local access: http://localhost:{self.port}")
            
            # Obtener IP pública
            try:
                import requests
                public_ip = requests.get('https://api.ipify.org').text
                print(f"Public access: http://{public_ip}:{self.port}")
            except:
                print("Could not determine public IP")
            
            # Mantener el servidor corriendo
            while True:
                await asyncio.sleep(3600)
        
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(start_server())
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            loop.close()

    async def handle_options(self, request):
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return web.Response(headers=headers)

if __name__ == '__main__':
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Servidor de túnel para acceso remoto')
    parser.add_argument('--port', type=int, default=8080, help='Puerto para el servidor (default: 8080)')
    
    args = parser.parse_args()
    
    try:
        server = TunnelServer(port=args.port)
        print(f"\nIniciando servidor de túnel en el puerto {args.port}...")
        print("Presiona Ctrl+C para detener el servidor\n")
        server.run()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError fatal: {e}")
        sys.exit(1)
