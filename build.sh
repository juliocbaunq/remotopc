#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar dependencias de Python
pip install -r requirements.txt

# Crear directorios necesarios si no existen
mkdir -p logs
