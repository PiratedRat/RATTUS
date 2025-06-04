import uuid
import paho.mqtt.client as mqtt

broker = "broker.hivemq.com"
topic = "anonymous/i2c/bus"

def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNECTED TO BROKER")
    client.subscribe(topic)

def on_message(client, userdata, message):
    text = message.payload.decode("utf-8").strip()
    print("SERVER CHAT:", text)

client = mqtt.Client(
    client_id=str(uuid.uuid4()),  # Generate unique client ID
    protocol=mqtt.MQTTv5
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, 1883, 60)
client.loop_start()  # Use loop_start() so you can run the input loop in parallel

# Infinite loop for sending messages
try:
    while True:
        msg = input("You: ")
        if msg.strip() != "":
            client.publish(topic, msg)
except KeyboardInterrupt:
    print("\nDisconnected by user")
    client.loop_stop()
    client.disconnect()
