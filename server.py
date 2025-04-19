from flask import Flask, render_template
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime
from flask_sock import Sock
import pyautogui
import base64
from io import BytesIO
from PIL import Image
import json
import asyncio
import threading
import time
from tunnel_client import TunnelClient

# Initialize Firebase
cred = credentials.Certificate('serviciofirebase.json')
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

app = Flask(__name__)
sock = Sock(app)

# Configuración de PyAutoGUI
pyautogui.FAILSAFE = True

# Funciones de utilidad para Firestore
def get_firestore_data(collection_name='servers'):
    docs = db.collection(collection_name).stream()
    return {doc.id: doc.to_dict() for doc in docs}

def update_firestore_data(data, collection_name='servers', document_id='current'):
    doc_ref = db.collection(collection_name).document(document_id)
    doc_ref.set(data, merge=True)

@app.route('/')
def home():
    return render_template('index.html')

def send_screen(ws):
    """Función auxiliar para capturar y enviar la pantalla"""
    try:
        # Capturar pantalla
        screenshot = pyautogui.screenshot()
        screen_size = pyautogui.size()
        
        # Convertir a JPEG con menor calidad
        buffered = BytesIO()
        screenshot.save(buffered, format="JPEG", quality=30)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Enviar al cliente
        response = {
            'type': 'screen',
            'data': img_str,
            'screen_width': screen_size[0],
            'screen_height': screen_size[1],
            'timestamp': datetime.now().isoformat()
        }
        ws.send(json.dumps(response))
        print(f"Pantalla enviada: {screen_size[0]}x{screen_size[1]}")
    except Exception as e:
        print(f"Error enviando pantalla: {e}")

@sock.route('/ws')
def websocket(ws):
    try:
        # Registrar conexión en Firestore
        update_connection_status(True)
        print("Nueva conexión WebSocket establecida")
        
        # Enviar pantalla inicial
        send_screen(ws)
        
        # Configurar temporizador para envío periódico
        last_screen_time = time.time()
        screen_interval = 1.0  # segundos entre actualizaciones
        
        while True:
            try:
                # Verificar si es tiempo de enviar pantalla
                current_time = time.time()
                if current_time - last_screen_time >= screen_interval:
                    send_screen(ws)
                    last_screen_time = current_time
                
                # Recibir comandos del cliente
                data = ws.receive()
                command = json.loads(data)
                print(f"Comando recibido: {command['action']}")
                
                if command['action'] == 'get_screen':
                    print("Capturando pantalla...")
                    # Capturar pantalla
                    screenshot = pyautogui.screenshot()
                    # Obtener dimensiones de la pantalla
                    screen_size = pyautogui.size()
                    
                    # Convertir a JPEG con menor calidad para mejor rendimiento
                    buffered = BytesIO()
                    screenshot.save(buffered, format="JPEG", quality=30)
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    # Enviar respuesta al cliente
                    response = {
                        'type': 'screen',
                        'data': img_str,
                        'screen_width': screen_size[0],
                        'screen_height': screen_size[1],
                        'timestamp': datetime.now().isoformat()
                    }
                    ws.send(json.dumps(response))
                    print(f"Pantalla enviada: {screen_size[0]}x{screen_size[1]}")
                    
                elif command['action'] == 'mouse_move':
                    x, y = command.get('x', 0), command.get('y', 0)
                    print(f"Moviendo mouse a: ({x}, {y})")
                    pyautogui.moveTo(x, y)
                    ws.send(json.dumps({'type': 'mouse_moved', 'x': x, 'y': y}))
                    
                elif command['action'] == 'mouse_click':
                    button = command.get('button', 'left')
                    print(f"Click del mouse: {button}")
                    pyautogui.click(button=button)
                    ws.send(json.dumps({'type': 'mouse_clicked', 'button': button}))
                    
                elif command['action'] == 'key_press':
                    key = command.get('key')
                    if key:
                        print(f"Tecla presionada: {key}")
                        pyautogui.press(key)
                        ws.send(json.dumps({'type': 'key_pressed', 'key': key}))
                    
            except json.JSONDecodeError as e:
                print(f"Error decodificando JSON: {e}")
                continue
            except Exception as e:
                print(f"Error procesando comando: {e}")
                continue
                
    except Exception as e:
        print(f"Error en WebSocket: {e}")
    finally:
        print("Conexión WebSocket cerrada")
        update_connection_status(False)

@app.route('/add_data', methods=['POST'])
def add_data():
    try:
        # Ejemplo de cómo agregar datos a Firestore
        test_data = {
            'test_field': 'test_value',
            'timestamp': datetime.now()
        }
        update_firestore_data(test_data, 'test_collection', 'test_doc')
        return jsonify({
            "message": "Data added successfully",
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "message": "Error adding data",
            "error": str(e),
            "status": "error"
        }), 500

@app.route('/status')
def status():
    return jsonify({
        "server_status": "running",
        "timestamp": "online"
    })

def update_connection_status(is_connected):
    # Update the server information in Firestore
    server_data = {
        'connected': is_connected,
        'last_updated': datetime.now(),
        'status': 'online' if is_connected else 'disconnected'
    }
    doc_ref = db.collection('remote_connections').document('status')
    doc_ref.set(server_data, merge=True)

def generate_tunnel_id():
    # Generar un ID único para el túnel
    import uuid
    tunnel_id = str(uuid.uuid4())[:8]  # Usar los primeros 8 caracteres del UUID
    
    # Guardar el ID en Firebase
    doc_ref = db.collection('tunnels').document(tunnel_id)
    doc_ref.set({
        'tunnel_id': tunnel_id,
        'created_at': datetime.now(),
        'type': 'remote_desktop',
        'status': 'initializing'
    })
    
    return tunnel_id

def get_server_info():
    import requests
    try:
        # Obtener IP pública
        public_ip = requests.get('https://api.ipify.org').text
        return {
            'local_url': 'localhost:8080',
            'public_url': f'{public_ip}:8080',
            'public_ip': public_ip
        }
    except:
        return {
            'local_url': 'localhost:8080',
            'public_ip': None,
            'public_url': None
        }

def start_ngrok_tunnel():
    from ngrok_tunnel import NgrokTunnel
    
    # Crear administrador de túnel ngrok
    tunnel = NgrokTunnel(port=5000)
    
    # Iniciar túnel en un hilo separado
    tunnel_thread = threading.Thread(
        target=tunnel.start,
        daemon=True
    )
    tunnel_thread.start()

def start_server():
    print("Iniciando servidor de escritorio remoto...")
    
    # Actualizar estado en Firebase
    main_doc_ref = db.collection('remote_desktop').document('main')
    main_doc_ref.set({
        'last_startup': datetime.now(),
        'status': 'starting',
        'server_version': '1.0',
        'tunnel_type': 'ngrok'
    })
    
    # Iniciar el túnel ngrok
    start_ngrok_tunnel()
    
    print("\nInformación del túnel en Firebase:")
    print("Colección: 'tunnels'")
    print("Documento: 'status'")
    print("\nEspera unos segundos mientras se establece el túnel...")
    
    # Iniciar servidor web en puerto local
    print("\nIniciando servidor web en puerto 5000...")
    app.run(port=5000)

if __name__ == '__main__':
    start_server()
