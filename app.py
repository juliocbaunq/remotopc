from flask import Flask, render_template, jsonify
from flask_sock import Sock
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import json
import time
import threading
from datetime import datetime
import os
import sys
import platform

# Verificar si tenemos display
HAS_DISPLAY = bool(os.environ.get('DISPLAY')) if platform.system() != 'Windows' else True

# Importar PyAutoGUI solo si tenemos display
pyautogui = None
if HAS_DISPLAY:
    try:
        import pyautogui as pag
        pyautogui = pag
        pyautogui.FAILSAFE = True
        print("PyAutoGUI inicializado correctamente")
    except Exception as e:
        print(f"Error al importar PyAutoGUI: {e}")
        pyautogui = None
else:
    print("No hay display disponible para PyAutoGUI")

def create_info_image():
    """Crear una imagen con información del servidor"""
    width = 800
    height = 400
    img = Image.new('RGB', (width, height), color='#f0f0f0')
    draw = ImageDraw.Draw(img)
    
    # Dibujar un mensaje
    text = "Servicio de Escritorio Remoto\n\n"
    text += "Este servicio debe ejecutarse localmente\n"
    text += "para tener acceso al escritorio.\n\n"
    text += "Por favor, descargue y ejecute\n"
    text += "la aplicación en su computadora local."
    
    # Dibujar el texto centrado
    text_bbox = draw.multiline_textbbox((0, 0), text, align='center')
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    x = (width - text_width) / 2
    y = (height - text_height) / 2
    
    draw.multiline_text((x, y), text, fill='#333333', align='center')
    
    return img

# Determinar si estamos en un entorno de servidor (Render)
IS_SERVER = os.environ.get('RENDER') == 'true' or not os.environ.get('DISPLAY')

# Solo intentar importar PyAutoGUI si no estamos en el servidor
if not IS_SERVER:
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
    except Exception as e:
        print(f"Error al importar PyAutoGUI: {e}")
        IS_SERVER = True

# Inicializar Flask
app = Flask(__name__)
sock = Sock(app)

# Ya no necesitamos esta línea, la configuración se hace arriba

def create_error_image(error_message):
    """Crear una imagen con mensaje de error"""
    width = 800
    height = 400
    img = Image.new('RGB', (width, height), color='#f0f0f0')
    draw = ImageDraw.Draw(img)
    
    # Dibujar mensaje de error
    draw.text((width/2, height/2), f"Error: {error_message}", 
              fill='#FF0000', anchor="mm")
    
    return img, (width, height)

def get_screen():
    """Obtener la pantalla usando PyAutoGUI"""
    try:
        if not pyautogui:
            return create_error_image("PyAutoGUI no está disponible")
        
        screenshot = pyautogui.screenshot()
        if not screenshot:
            return create_error_image("No se pudo capturar la pantalla")
            
        return screenshot, pyautogui.size()
    except Exception as e:
        print(f"Error capturando pantalla: {e}")
        return create_error_image(str(e))

def send_binary_response(ws, data):
    """Enviar respuesta binaria al cliente"""
    try:
        # Verificar si el cliente quiere modo binario
        if hasattr(ws, 'binary_mode') and ws.binary_mode:
            # Si es una imagen, enviar como bytes
            if isinstance(data.get('data'), str) and data.get('type') == 'screen':
                try:
                    img_bytes = base64.b64decode(data['data'])
                    ws.send(img_bytes)
                    return
                except Exception as e:
                    print(f"Error enviando imagen binaria: {e}")
        
        # Si no es binario o hubo error, enviar como JSON
        json_str = json.dumps(data)
        ws.send(json_str.encode('utf-8'))
    except Exception as e:
        print(f"Error enviando respuesta: {e}")

def send_screen(ws):
    """Función auxiliar para capturar y enviar la pantalla"""
    try:
        # Obtener imagen y dimensiones
        img, screen_size = get_screen()
        
        if not img or not screen_size:
            img, screen_size = create_error_image("Error obteniendo la imagen")
        
        # Convertir a JPEG
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=30)
        img_bytes = buffered.getvalue()
        img_str = base64.b64encode(img_bytes).decode()
        
        # Enviar al cliente
        send_binary_response(ws, {
            'type': 'screen',
            'data': img_str,
            'screen_width': screen_size[0],
            'screen_height': screen_size[1],
            'timestamp': datetime.now().isoformat(),
            'error': img == None
        })
        print(f"Imagen enviada: {screen_size[0]}x{screen_size[1]}")
    except Exception as e:
        print(f"Error enviando pantalla: {e}")
        # Intentar enviar imagen de error
        try:
            error_img, error_size = create_error_image(str(e))
            buffered = BytesIO()
            error_img.save(buffered, format="JPEG", quality=30)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            send_binary_response(ws, {
                'type': 'screen',
                'data': img_str,
                'screen_width': error_size[0],
                'screen_height': error_size[1],
                'timestamp': datetime.now().isoformat(),
                'error': True
            })
        except Exception as e2:
            print(f"Error enviando imagen de error: {e2}")
            send_binary_response(ws, {
                'type': 'error',
                'message': str(e)
            })

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/status')
def status():
    return jsonify({
        'is_server': IS_SERVER,
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'timestamp': datetime.now().isoformat()
    })

def handle_mouse_move(ws, x, y):
    """Manejar movimiento del mouse"""
    try:
        if not pyautogui:
            raise Exception("PyAutoGUI no está disponible")
        pyautogui.moveTo(x, y)
        ws.send(json.dumps({'type': 'mouse_moved', 'x': x, 'y': y}))
    except Exception as e:
        print(f"Error moviendo mouse: {e}")
        ws.send(json.dumps({'type': 'error', 'message': str(e)}))

def handle_mouse_click(ws, button):
    """Manejar click del mouse"""
    try:
        if not pyautogui:
            raise Exception("PyAutoGUI no está disponible")
        pyautogui.click(button=button)
        ws.send(json.dumps({'type': 'mouse_clicked', 'button': button}))
    except Exception as e:
        print(f"Error haciendo click: {e}")
        ws.send(json.dumps({'type': 'error', 'message': str(e)}))

def handle_key_press(ws, key):
    """Manejar presionado de tecla"""
    try:
        if not pyautogui:
            raise Exception("PyAutoGUI no está disponible")
        pyautogui.press(key)
        ws.send(json.dumps({'type': 'key_pressed', 'key': key}))
    except Exception as e:
        print(f"Error presionando tecla: {e}")
        ws.send(json.dumps({'type': 'error', 'message': str(e)}))

def process_command(ws, data):
    """Procesar un comando recibido del cliente"""
    try:
        # Si los datos son binarios, decodificar
        if isinstance(data, bytes):
            data = data.decode('utf-8')
            
        command = json.loads(data)
        action = command.get('action')
        
        if action == 'get_screen':
            send_screen(ws)
        elif action == 'set_binary':
            # El cliente solicita modo binario
            ws.binary_mode = command.get('enable', False)
            print(f"Modo binario: {ws.binary_mode}")
        elif action == 'mouse_move':
            handle_mouse_move(ws, command.get('x', 0), command.get('y', 0))
        elif action == 'mouse_click':
            handle_mouse_click(ws, command.get('button', 'left'))
        elif action == 'key_press':
            handle_key_press(ws, command.get('key'))
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error decodificando comando: {e}")
    except Exception as e:
        print(f"Error procesando comando: {e}")

@sock.route('/ws')
def websocket(ws):
    try:
        print("Nueva conexión WebSocket establecida")
        
        # Enviar pantalla inicial
        send_screen(ws)
        
        # Configurar temporizador
        last_screen_time = time.time()
        screen_interval = 0.1  # 100ms entre frames
        
        while True:
            try:
                # Actualizar pantalla periódicamente
                current_time = time.time()
                if current_time - last_screen_time >= screen_interval:
                    send_screen(ws)
                    last_screen_time = current_time
                
                # Procesar comandos sin bloquear
                data = ws.receive()
                if data:
                    process_command(ws, data)
                    
                # Pequeña pausa para no saturar la CPU
                time.sleep(0.01)
                    
            except Exception as e:
                print(f"Error en el bucle principal: {e}")
                if "connection" in str(e).lower():
                    break
                time.sleep(0.1)  # Esperar un poco si hay error
                
    except Exception as e:
        print(f"Error en WebSocket: {e}")
    finally:
        print("Conexión WebSocket cerrada")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
