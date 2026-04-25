import json
import os
from datetime import datetime

from aiokafka import AIOKafkaProducer
from dotenv import load_dotenv

load_dotenv()


KAFKA_BOOTSTRAP_SERVICES=os.getenv("KAFKA_BOOTSTRAP_SERVERS","localhost:9092")

KAFKA_TOPIC=os.getenv("KAFKA_TOPIC","activity_logs")

kafka_producer: AIOKafkaProducer = None


async def start_kafka_producer():

    global kafka_producer

    kafka_producer=AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVICES,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    await kafka_producer.start()

    print(f"kafka producer started:{kafka_producer}")

async def stop_kafka_producer():
    global kafka_producer

    if kafka_producer:
        await kafka_producer.stop()
        print("Kafka producer stopped")



async def publish_log(log_data:dict):

    if not kafka_producer:
        raise RuntimeError("kafka producer not initialized")

    try:
        await kafka_producer.send(KAFKA_TOPIC, value=log_data)
        print(f"Published to Kafka: {log_data}")

    except Exception as e:
        print(f"Failed to publish to Kafka: {e}")
        raise



def get_topic_name():
    return KAFKA_TOPIC

