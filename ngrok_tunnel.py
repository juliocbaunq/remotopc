from pyngrok import ngrok
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import logging
import threading
import time

class NgrokTunnel:
    def __init__(self, port=5000):
        self.port = port
        self.public_url = None
        self.tunnel = None
        self.running = False
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('NgrokTunnel')
        
        # Inicializar Firebase
        if not firebase_admin._apps:
            cred = credentials.Certificate('serviciofirebase.json')
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()
    
    def _update_status(self, status, url=None, error=None):
        """Actualizar estado en Firebase"""
        doc_ref = self.db.collection('tunnels').document('status')
        data = {
            'status': status,
            'last_updated': datetime.now(),
            'local_port': self.port
        }
        
        if url:
            data['public_url'] = url
        if error:
            data['error'] = str(error)
            
        doc_ref.set(data, merge=True)
    
    def start(self):
        """Iniciar el túnel ngrok"""
        try:
            self.logger.info(f"Iniciando túnel para el puerto {self.port}...")
            self._update_status('starting')
            
            # Iniciar el túnel
            self.tunnel = ngrok.connect(self.port, "http")
            self.public_url = self.tunnel.public_url
            self.running = True
            
            self.logger.info(f"Túnel establecido en: {self.public_url}")
            self._update_status('connected', self.public_url)
            
            # Monitorear el túnel
            self._monitor_tunnel()
            
        except Exception as e:
            self.logger.error(f"Error al iniciar el túnel: {e}")
            self._update_status('error', error=str(e))
            raise
    
    def _monitor_tunnel(self):
        """Monitorear el estado del túnel"""
        def monitor():
            while self.running:
                try:
                    # Verificar si el túnel está activo
                    tunnels = ngrok.get_tunnels()
                    if not any(t.public_url == self.public_url for t in tunnels):
                        self.logger.warning("Túnel inactivo, intentando reconectar...")
                        self._update_status('reconnecting')
                        self.tunnel = ngrok.connect(self.port, "http")
                        self.public_url = self.tunnel.public_url
                        self._update_status('connected', self.public_url)
                except Exception as e:
                    self.logger.error(f"Error en monitoreo del túnel: {e}")
                    self._update_status('error', error=str(e))
                    break
                    
                time.sleep(30)  # Verificar cada 30 segundos
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def stop(self):
        """Detener el túnel"""
        if self.tunnel:
            self.running = False
            ngrok.disconnect(self.tunnel.public_url)
            self._update_status('stopped')
            self.logger.info("Túnel detenido")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Túnel ngrok para acceso remoto')
    parser.add_argument('--port', type=int, default=5000, help='Puerto local (default: 5000)')
    
    args = parser.parse_args()
    
    tunnel = NgrokTunnel(args.port)
    
    try:
        print(f"\nIniciando túnel para el puerto {args.port}...")
        print("Espera mientras se establece la conexión...")
        tunnel.start()
        
        # Mantener el programa corriendo
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nDeteniendo túnel...")
        tunnel.stop()
    except Exception as e:
        print(f"\nError: {e}")
        tunnel.stop()

if __name__ == '__main__':
    main()
