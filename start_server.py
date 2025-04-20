import os
import sys
import subprocess
import signal
import time

def run_server():
    try:
        # Obtener el directorio actual
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Configurar el comando de gunicorn
        cmd = [
            "gunicorn",
            "--config", "gunicorn_config.py",
            "--worker-class", "gevent",
            "--workers", "4",
            "--bind", "0.0.0.0:8000",
            "--log-level", "info",
            "--reload",
            "app:app"  # Asumiendo que tu aplicación Flask está en app.py y la instancia se llama app
        ]
        
        # Iniciar gunicorn
        print("\nIniciando servidor con gunicorn...")
        print("Configuración:")
        print(f"- Workers: 4")
        print(f"- Puerto: 8000")
        print(f"- Modo: Desarrollo (auto-reload activado)")
        print("\nPara detener el servidor, presiona Ctrl+C\n")
        
        process = subprocess.Popen(
            cmd,
            cwd=current_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Manejar señales para una terminación limpia
        def signal_handler(signum, frame):
            print("\nDeteniendo servidor...")
            process.terminate()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Monitorear la salida del proceso
        while True:
            output = process.stderr.readline()
            if output:
                print(output.decode().strip())
            
            # Verificar si el proceso sigue vivo
            if process.poll() is not None:
                break
            
            time.sleep(0.1)
            
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server()
