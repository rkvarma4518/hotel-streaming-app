"""Read the same hub with the KAFKA protocol (needs Event Hubs Standard tier).
    pip install kafka-python
    KAFKA_NAMESPACE=<ns> KAFKA_CONN="<namespace-level connection string>" python examples/kafka_consumer.py
"""
import os
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "hotel-events",  # topic == event hub name
    bootstrap_servers=f"{os.environ['KAFKA_NAMESPACE']}.servicebus.windows.net:9093",
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_plain_username="$ConnectionString",
    sasl_plain_password=os.environ["KAFKA_CONN"],
    group_id="kafka-learners",
    auto_offset_reset="earliest",
)
for msg in consumer:
    print(f"p{msg.partition} @{msg.offset}", msg.value.decode())
