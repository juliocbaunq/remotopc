import multiprocessing

# Configuración del servidor
bind = "0.0.0.0:8000"  # Puerto en el que escuchará gunicorn
workers = multiprocessing.cpu_count() * 2 + 1  # Número de workers
worker_class = "gevent"  # Usar gevent para soporte de WebSocket
worker_connections = 1000

# Configuración de timeouts
timeout = 120  # Timeout en segundos
keepalive = 5  # Mantener conexiones vivas

# Configuración de logging
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"

# Configuración de SSL/TLS (descomentar si se usa HTTPS)
# keyfile = "path/to/keyfile"
# certfile = "path/to/certfile"

# Configuración de rendimiento
worker_tmp_dir = "/dev/shm"  # Usar memoria compartida para archivos temporales
max_requests = 1000  # Reiniciar workers después de este número de solicitudes
max_requests_jitter = 50  # Agregar aleatoriedad al reinicio

# Configuración de desarrollo
reload = True  # Recargar automáticamente cuando el código cambia
reload_engine = "auto"

# Configuración de seguridad
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
