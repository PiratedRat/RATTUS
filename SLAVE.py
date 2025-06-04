import uuid
import paho.mqtt.client as mqtt

broker = "broker.hivemq.com"
topic = "anonymous/i2c/bus"

mac = uuid.getnode()
device_id = f"{mac:012x}"[-5:].upper()
reserved = False

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

client = mqtt.Client(
    client_id="",
    protocol=mqtt.MQTTv5
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, 1883, 60)
client.loop_forever()