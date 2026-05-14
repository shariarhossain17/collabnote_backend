import asyncio
import json
import os
from datetime import datetime

from aiokafka import AIOKafkaConsumer
from dotenv import load_dotenv

from .mongodb import connect_to_mongodb, get_mongodb

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "activity_logs")
KAFKA_GROUP_ID = "log_consumer_group"


async def consume_logs():
    """
    Kafka consumer that processes log events and saves to MongoDB
    """
    # Connect to MongoDB
    await connect_to_mongodb()
    mongodb = get_mongodb()

    # Create Kafka consumer
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',  # Start from beginning if no offset
        enable_auto_commit=True
    )

    await consumer.start()
    print(f"Kafka consumer started. Listening to topic: {KAFKA_TOPIC}")

    try:
        async for message in consumer:
            log_data = message.value

            print(f"Received message: {log_data}")

            # Convert timestamp string back to datetime
            if "timestamp" in log_data and isinstance(log_data["timestamp"], str):
                log_data["timestamp"] = datetime.fromisoformat(log_data["timestamp"])

            # Save to MongoDB
            result = await mongodb.activity_logs.insert_one(log_data)
            print(f"Saved to MongoDB with ID: {result.inserted_id}")

    except Exception as e:
        print(f"Error in consumer: {e}")
    finally:
        await consumer.stop()
        print("Consumer stopped")


if __name__ == "__main__":
    print("Starting Kafka consumer...")
    asyncio.run(consume_logs())
