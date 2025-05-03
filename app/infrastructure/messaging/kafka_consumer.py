import asyncio
from kafka import KafkaConsumer  # Direct import with no fallback
import json
import os
import logging
from typing import Callable, Awaitable
from ...application.services.query_service import QueryService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Kafka client logging to reduce verbosity
for logger_name in ['kafka', 'kafka.client', 'kafka.conn', 'kafka.protocol', 
                    'kafka.coordinator', 'kafka.consumer']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

class KafkaConsumerService:
    def __init__(self, query_service: QueryService):
        self.query_service = query_service
        self.consumer = None
        self._initialize_consumer()

    def _initialize_consumer(self):
        """Initialize Kafka consumer with no fallback - will throw exception if Kafka is unavailable"""
        try:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            logger.info(f"Initializing Kafka consumer with bootstrap servers: {bootstrap_servers}")
            
            self.consumer = KafkaConsumer(
                'rag_queries',
                bootstrap_servers=bootstrap_servers,
                group_id='rag_consumer_group',
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                # Reduce logging and connection timeouts
                api_version_auto_timeout_ms=5000,  # Shorter timeout for API version detection
                session_timeout_ms=10000,  # Shorter session timeout
                request_timeout_ms=15000,  # Shorter request timeout
                connections_max_idle_ms=60000  # Shorter connection idle time
            )
            logger.info("Kafka consumer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            # Re-raise the exception to prevent application from continuing without Kafka
            raise

    async def start_consuming(self):
        """Start consuming messages from Kafka"""
        if not self.consumer:
            error_msg = "Kafka consumer not initialized"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            logger.info("Starting to consume messages from Kafka...")
            while True:
                try:
                    # Use poll with a timeout to avoid blocking indefinitely
                    messages = self.consumer.poll(timeout_ms=1000)  # Poll for 1 second
                    
                    if not messages:
                        await asyncio.sleep(0.1)  # Short sleep if no messages
                        continue

                    for tp, records in messages.items():
                        for record in records:
                            try:
                                query_data = record.value
                                query_id = query_data['query_id']
                                query = query_data['query']

                                logger.info(f"Processing query {query_id}")
                                # Process the query asynchronously
                                asyncio.create_task(
                                    self.query_service.process_async_query(query_id, query)
                                )
                            except Exception as e:
                                logger.error(f"Error processing message: {e} - Data: {record.value}")

                except Exception as e:
                    logger.error(f"Error polling Kafka: {e}")
                    # Wait before retrying
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("Consumption task cancelled.")
        except Exception as e:
            logger.error(f"Critical error in Kafka consumer loop: {e}")
            raise  # Re-raise the exception instead of handling it silently
        finally:
            await self.stop()

    async def stop(self):
        """Stop the Kafka consumer"""
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka consumer: {e}")
                raise  # Re-raise the exception
        self.consumer = None