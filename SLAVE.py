import uuid
import paho.mqtt.client as mqtt
import base64
from io import BytesIO
from PIL import Image
import mss

broker = "broker.hivemq.com"
topic = "anonymous/i2c/bus"

mac = uuid.getnode()
device_id = f"{mac:012x}"[-5:].upper()
reserved = False

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

def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNECTED TO BROKER")
    client.subscribe(topic)

def on_message(client, userdata, message):
    global reserved  # Needed to modify the global variable

    text = message.payload.decode("utf-8").strip()
    print("SERVER CHAT:", text)

    if "WHO" in text:
        client.publish(topic, device_id)

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
            client.publish(topic, f"{device_id} CANCELED")
        elif target == device_id and not reserved:
            client.publish(topic, f"{device_id} ALREADY CANCELED")

    if "GET" in text:
        parts = text.removeprefix("GET ").strip().split()
        action = parts[0]
        target = parts[1]
        if target == device_id and action == "SC" and reserved:
            b64_str = screenshot_to_base64(format='WEBP', quality=50)
            b64_size_kb = len(b64_str.encode('utf-8')) / 1024
            print(str(b64_size_kb) + "Kb")
            client.publish(topic, f"{device_id} {b64_str}")
        elif target == device_id and action == "CC" and reserved:
            pass
        elif not reserved:
            client.publish(topic, f"{device_id} NOT RESERVED")

client = mqtt.Client(
    client_id="",
    protocol=mqtt.MQTTv5
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, 1883, 60)
client.loop_forever()