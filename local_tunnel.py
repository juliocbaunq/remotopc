import subprocess
import threading
import re
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import logging

class LocalTunnel:
    def __init__(self, local_port=5000):
        self.local_port = local_port
        self.public_url = None
        self.process = None
        self.running = False
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('LocalTunnel')
        
        # Inicializar Firebase
        if not firebase_admin._apps:
            cred = credentials.Certificate('serviciofirebase.json')
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()
    
    def _update_status(self, status, url=None):
        """Actualizar estado en Firebase"""
        doc_ref = self.db.collection('tunnels').document('status')
        data = {
            'status': status,
            'last_updated': datetime.now(),
            'local_port': self.local_port
        }
        
        if url:
            data['public_url'] = url
        
        doc_ref.set(data, merge=True)
        
    def _monitor_output(self, process):
        """Monitorear la salida del proceso para obtener la URL"""
        while self.running:
            line = process.stdout.readline()
            if not line:
                break
                
            line = line.decode('utf-8').strip()
            print(line)  # Mostrar la salida en consola
            
            # Buscar la URL en la salida
            if "tunneled with tls termination" in line:
                match = re.search(r'https://[^\s]+', line)
                if match:
                    self.public_url = match.group(0)
                    self.logger.info(f"URL pública obtenida: {self.public_url}")
                    self._update_status('connected', self.public_url)
    
    def start(self):
        """Iniciar el túnel local"""
        try:
            self.logger.info(f"Iniciando túnel para el puerto {self.local_port}...")
            self._update_status('starting')
            
            # Iniciar el proceso de SSH
            cmd = f"ssh -R 80:localhost:{self.local_port} nokey@localhost.run"
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            )
            
            self.running = True
            
            # Monitorear la salida en un hilo separado
            monitor_thread = threading.Thread(target=self._monitor_output, args=(self.process,))
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # Esperar a que el proceso termine
            self.process.wait()
            
        except Exception as e:
            self.logger.error(f"Error al iniciar el túnel: {e}")
            self._update_status('error')
            raise
        finally:
            self.running = False
    
    def stop(self):
        """Detener el túnel"""
        if self.process:
            self.running = False
            self.process.terminate()
            self._update_status('stopped')
            self.logger.info("Túnel detenido")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Túnel local para acceso remoto')
    parser.add_argument('--port', type=int, default=5000, help='Puerto local (default: 5000)')
    
    args = parser.parse_args()
    
    tunnel = LocalTunnel(args.port)
    
    try:
        print(f"\nIniciando túnel para el puerto {args.port}...")
        print("Espera mientras se establece la conexión...")
        tunnel.start()
    except KeyboardInterrupt:
        print("\nDeteniendo túnel...")
        tunnel.stop()
    except Exception as e:
        print(f"\nError: {e}")
        tunnel.stop()

if __name__ == '__main__':
    main()
