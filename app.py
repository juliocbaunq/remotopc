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
import json
import time
import base64
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_sock import Sock
from PIL import Image, ImageDraw, ImageFont
from mss import mss
from pynput import mouse, keyboard

# Inicializar Flask
app = Flask(__name__)
sock = Sock(app)

# Verificar si estamos en un servidor
IS_SERVER = os.environ.get('RENDER') is not None

# Variables globales para controladores
sct = None
mouse_controller = None
keyboard_controller = None
SCREEN_CONTROLLER_AVAILABLE = False

# Inicializar controladores si no estamos en servidor
if not IS_SERVER:
    try:
        sct = mss()
        mouse_controller = mouse.Controller()
        keyboard_controller = keyboard.Controller()
        SCREEN_CONTROLLER_AVAILABLE = True
    except Exception as e:
        print(f"Error inicializando controladores: {e}")
        IS_SERVER = True

# Rutas para fuentes
font_path = os.path.join(os.path.dirname(__file__), 'static', 'fonts', 'arial.ttf')
if not os.path.exists(font_path):
    font_path = None

def create_info_image():
    """Crear una imagen con información del servidor"""
    width = 800
    height = 400
    img = Image.new('RGB', (width, height), color='#f0f0f0')
    draw = ImageDraw.Draw(img)
    
    # Intentar usar la fuente especificada o la default
    try:
        if font_path:
            font = ImageFont.truetype(font_path, 20)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    message = "Este servicio debe ejecutarse localmente\npara tener acceso completo al escritorio remoto."
    draw.text((width/2, height/2), message, 
              fill='#000000', font=font, anchor="mm")
    
    return img, (width, height)

def create_error_image(error_message):
    """Crear una imagen con mensaje de error"""
    width = 800
    height = 400
    img = Image.new('RGB', (width, height), color='#f0f0f0')
    draw = ImageDraw.Draw(img)
    
    try:
        if font_path:
            font = ImageFont.truetype(font_path, 20)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    draw.text((width/2, height/2), f"Error: {error_message}", 
              fill='#FF0000', font=font, anchor="mm")
    
    return img, (width, height)

def get_screen():
    """Capturar la pantalla y retornar imagen y dimensiones"""
    try:
        if not SCREEN_CONTROLLER_AVAILABLE:
            return create_info_image()
            
        # Capturar pantalla usando mss
        with mss() as sct:
            monitor = sct.monitors[0]  # Monitor principal
            screenshot = sct.grab(monitor)
            # Convertir a PIL Image
            img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
            return img, img.size
    except Exception as e:
        print(f"Error capturando pantalla: {e}")
        return create_error_image(str(e))

def send_binary_response(ws, data):
    """Enviar respuesta binaria al cliente"""
    try:
        # Si es una imagen, convertir a base64
        if data.get('type') == 'screen' and isinstance(data.get('image'), Image.Image):
            try:
                # Convertir imagen a bytes JPEG
                buffered = BytesIO()
                data['image'].save(buffered, format="JPEG", quality=70)
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # Reemplazar imagen con string base64
                data['data'] = img_str
                del data['image']
            except Exception as e:
                print(f"Error convirtiendo imagen: {e}")
                return
        
        # Enviar como JSON
        json_str = json.dumps(data)
        ws.send(json_str)
    except Exception as e:
        print(f"Error enviando respuesta: {e}")

def send_screen(ws):
    """Función auxiliar para capturar y enviar la pantalla"""
    try:
        # Obtener imagen y dimensiones
        img, screen_size = get_screen()
        
        if not img or not screen_size:
            img, screen_size = create_error_image("Error obteniendo la imagen")
        
        # Enviar al cliente
        send_binary_response(ws, {
            'type': 'screen',
            'image': img,  # La imagen será convertida en send_binary_response
            'screen_width': screen_size[0],
            'screen_height': screen_size[1],
            'timestamp': datetime.now().isoformat(),
            'error': False
        })
        print(f"Imagen enviada: {screen_size[0]}x{screen_size[1]}")
    except Exception as e:
        print(f"Error enviando pantalla: {e}")
        try:
            # Crear y enviar imagen de error
            error_img, error_size = create_error_image(str(e))
            send_binary_response(ws, {
                'type': 'screen',
                'image': error_img,
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
        'platform': os.name,
        'python_version': os.sys.version,
        'timestamp': datetime.now().isoformat()
    })

def handle_mouse_move(ws, x, y):
    """Manejar movimiento del mouse"""
    try:
        if SCREEN_CONTROLLER_AVAILABLE:
            mouse_controller.position = (x, y)
            send_binary_response(ws, {
                'type': 'mouse_moved',
                'x': x,
                'y': y
            })
    except Exception as e:
        print(f"Error moviendo mouse: {e}")
        send_binary_response(ws, {
            'type': 'error',
            'message': str(e)
        })

def handle_mouse_click(ws, button):
    """Manejar click del mouse"""
    try:
        if SCREEN_CONTROLLER_AVAILABLE:
            if button == 'left':
                mouse_controller.click(mouse.Button.left)
            elif button == 'right':
                mouse_controller.click(mouse.Button.right)
            elif button == 'middle':
                mouse_controller.click(mouse.Button.middle)
                
            send_binary_response(ws, {
                'type': 'mouse_clicked',
                'button': button
            })
    except Exception as e:
        print(f"Error haciendo click: {e}")
        send_binary_response(ws, {
            'type': 'error',
            'message': str(e)
        })

def handle_key_press(ws, key):
    """Manejar presión de tecla"""
    try:
        if SCREEN_CONTROLLER_AVAILABLE:
            # Manejar teclas especiales
            special_keys = {
                'Enter': keyboard.Key.enter,
                'Backspace': keyboard.Key.backspace,
                'Tab': keyboard.Key.tab,
                'Space': keyboard.Key.space,
                'Escape': keyboard.Key.esc,
                'Delete': keyboard.Key.delete,
                'ArrowUp': keyboard.Key.up,
                'ArrowDown': keyboard.Key.down,
                'ArrowLeft': keyboard.Key.left,
                'ArrowRight': keyboard.Key.right
            }
            
            if key in special_keys:
                keyboard_controller.press(special_keys[key])
                keyboard_controller.release(special_keys[key])
            else:
                keyboard_controller.press(key)
                keyboard_controller.release(key)
                
            send_binary_response(ws, {
                'type': 'key_pressed',
                'key': key
            })
    except Exception as e:
        print(f"Error presionando tecla: {e}")
        send_binary_response(ws, {
            'type': 'error',
            'message': str(e)
        })

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
    """Manejar conexión WebSocket"""
    print("Nueva conexión WebSocket establecida")
    
    try:
        # Enviar pantalla inicial
        send_screen(ws)
        
        while True:
            try:
                # Recibir comando del cliente
                data = ws.receive()
                if not data:
                    continue
                
                # Procesar comando
                process_command(ws, data)
                
            except Exception as e:
                print(f"Error en WebSocket: {e}")
                if "connection" in str(e).lower():
                    break
                
    except Exception as e:
        print(f"Error en WebSocket: {e}")
    finally:
        print("Conexión WebSocket cerrada")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
