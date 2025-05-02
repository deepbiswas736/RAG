import asyncio
# Try to import Kafka with fallback
try:
    from kafka import KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    print("Warning: Kafka imports failed - consumer functionality will be limited")
    KafkaConsumer = None
    KAFKA_AVAILABLE = False
import json
import os
from typing import Callable, Awaitable
from ...application.services.query_service import QueryService

class KafkaConsumerService:
    def __init__(self, query_service: QueryService):
        self.query_service = query_service
        self.consumer = None
        self._initialize_consumer()

    def _initialize_consumer(self):
        if not KAFKA_AVAILABLE:
            print("Kafka is not available, consumer will not be initialized")
            return

        try:
            self.consumer = KafkaConsumer(
                'rag_queries',
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                group_id='rag_consumer_group',
                value_deserializer=lambda v: json.loads(v.decode('utf-8'))
            )
            print("Kafka consumer initialized successfully")
        except Exception as e:
            print(f"Error initializing Kafka consumer: {e}")
            self.consumer = None

    async def start_consuming(self):
        """Start consuming messages from Kafka"""
        if not self.consumer:
            print("Kafka consumer not available, consumption disabled")
            return

        try:
            print("Starting to consume messages from Kafka...")
            while True:
                try:
                    # Use poll with a timeout instead of next() to avoid blocking indefinitely
                    # and allow graceful shutdown checks
                    messages = self.consumer.poll(timeout_ms=1000) # Poll for 1 second
                    if not messages:
                        await asyncio.sleep(0.1) # Short sleep if no messages
                        continue

                    for tp, records in messages.items():
                        for record in records:
                            try:
                                query_data = record.value
                                query_id = query_data['query_id']
                                query = query_data['query']

                                print(f"Received query: {query_id}")
                                # Process the query asynchronously
                                asyncio.create_task(
                                    self.query_service.process_async_query(query_id, query)
                                )
                            except Exception as e:
                                print(f"Error processing message: {e} - Data: {record.value}")

                except Exception as e:
                    print(f"Error polling Kafka: {e}")
                    # Attempt to re-initialize consumer on certain errors if needed, or break
                    await asyncio.sleep(5) # Wait before retrying

        except asyncio.CancelledError:
             print("Consumption task cancelled.")
        except Exception as e:
            print(f"Critical error in Kafka consumer loop: {e}")
        finally:
            await self.stop()


    async def stop(self):
        """Stop the Kafka consumer"""
        if self.consumer:
            try:
                # Close might block, run in executor if it causes issues
                self.consumer.close()
                print("Kafka consumer closed")
            except Exception as e:
                print(f"Error closing Kafka consumer: {e}")
        self.consumer = None