# Remote Server Application

This is a Python-based remote server application that uses Flask and ngrok to create a publicly accessible endpoint without port forwarding.

## Setup

1. Install the requirements:
```
pip install -r requirements.txt
```

2. Sign up for a free ngrok account at https://ngrok.com/
3. Get your authtoken from ngrok dashboard
4. Set up your authtoken:
```
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

## Running the Server

Simply run:
```
python server.py
```

The server will start and display a public URL that can be accessed from anywhere.
