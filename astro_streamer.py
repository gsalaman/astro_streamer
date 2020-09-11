
import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server

import paho.mqtt.client as mqtt
import time

# Callback for simple message
def on_message(client, userdata, message):
  global camera

  print("message received: ", str(message.payload.decode("utf-8")))
  print("message topic=", message.topic)
  print("message qos=", message.qos)
  print("message retain flag=", message.retain)

  if (message.topic == "iso"):
    print("Got iso change")
    camera.iso = int(message.payload) 

  if (message.topic == "rot"):
    print("Got rotation change")
    camera.rotation = int(message.payload) 

  if (message.topic == "click"):
    print("taking picture")
    camera.capture('pic.jpg',use_video_port=True)

PAGE="""\
<html>
<head>
<title>Glenn's Raspberry Pi Stream</title>
</head>
<body>
<center><h1>Glenn's Raspberry Pi Stream</h1></center>
<center><img src="stream.mjpg" width="1024" height="768"></center>
</body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

#####################
# MAIN
#####################
broker_address="127.0.0.1"
client = mqtt.Client("AstroStreamer")
client.on_message=on_message
client.connect(broker_address)
client.loop_start()
client.subscribe("iso")
client.subscribe("rot")
client.subscribe("click")

#with picamera.PiCamera(resolution='1920x1080', framerate=24) as camera:
if True:
    camera = picamera.PiCamera(resolution='1920x1080',framerate=24)

    output = StreamingOutput()
    #Uncomment the next line to change your Pi's Camera rotation (in degrees)
    #camera.rotation = 90
    #camera.iso = 400 
    camera.start_recording(output, format='mjpeg')
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()

