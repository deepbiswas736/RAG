"""
Metrics utilities

This module provides utilities for tracking metrics related to Kafka operations.
"""

import time
import logging
import contextlib
from typing import Iterator
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Define metrics
MESSAGE_PRODUCED = Counter(
    "kafka_messages_produced_total",
    "Total number of messages produced to Kafka",
    ["topic"]
)

MESSAGE_CONSUMED = Counter(
    "kafka_messages_consumed_total",
    "Total number of messages consumed from Kafka",
    ["topic", "consumer_group"]
)

PRODUCER_ERRORS = Counter(
    "kafka_producer_errors_total",
    "Total number of errors when producing messages to Kafka",
    ["topic"]
)

CONSUMER_ERRORS = Counter(
    "kafka_consumer_errors_total",
    "Total number of errors when consuming messages from Kafka",
    ["topic", "consumer_group"]
)

PRODUCER_LATENCY = Histogram(
    "kafka_producer_latency_seconds",
    "Time taken to produce a message to Kafka",
    ["topic"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

CONSUMER_LATENCY = Histogram(
    "kafka_consumer_processing_latency_seconds",
    "Time taken to process a consumed message",
    ["topic", "consumer_group"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

KAFKA_CONNECTION_STATUS = Gauge(
    "kafka_connection_status",
    "Status of Kafka connection (1 = connected, 0 = disconnected)",
    ["bootstrap_servers"]
)

# Metrics tracking functions
def increment_message_produced(topic: str) -> None:
    """Increment the counter for messages produced."""
    MESSAGE_PRODUCED.labels(topic=topic).inc()

def increment_message_consumed(topic: str, consumer_group: str) -> None:
    """Increment the counter for messages consumed."""
    MESSAGE_CONSUMED.labels(topic=topic, consumer_group=consumer_group).inc()

def increment_producer_errors(topic: str) -> None:
    """Increment the counter for producer errors."""
    PRODUCER_ERRORS.labels(topic=topic).inc()

def increment_consumer_errors(topic: str, consumer_group: str) -> None:
    """Increment the counter for consumer errors."""
    CONSUMER_ERRORS.labels(topic=topic, consumer_group=consumer_group).inc()

def set_kafka_connection_status(bootstrap_servers: str, connected: bool) -> None:
    """Set the gauge for Kafka connection status."""
    KAFKA_CONNECTION_STATUS.labels(bootstrap_servers=bootstrap_servers).set(1 if connected else 0)

@contextlib.contextmanager
def track_producer_latency(topic: str) -> Iterator[None]:
    """Context manager for tracking producer latency."""
    start_time = time.time()
    try:
        yield
    finally:
        latency = time.time() - start_time
        PRODUCER_LATENCY.labels(topic=topic).observe(latency)

@contextlib.contextmanager
def track_consumer_latency(topic: str, consumer_group: str) -> Iterator[None]:
    """Context manager for tracking consumer processing latency."""
    start_time = time.time()
    try:
        yield
    finally:
        latency = time.time() - start_time
        CONSUMER_LATENCY.labels(topic=topic, consumer_group=consumer_group).observe(latency)
