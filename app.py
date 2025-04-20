from flask import Flask, render_template
from flask_sock import Sock
import pyautogui
import base64
from io import BytesIO
from PIL import Image
import json
import time
import threading
from datetime import datetime

# Inicializar Flask
app = Flask(__name__)
sock = Sock(app)

# Configuración de PyAutoGUI
pyautogui.FAILSAFE = True

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

@app.route('/')
def home():
    return render_template('index.html')

@sock.route('/ws')
def websocket(ws):
    try:
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
                    send_screen(ws)
                    
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
