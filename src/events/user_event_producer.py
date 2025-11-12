"""
Kafka producer used to publish user events
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

import json
from typing import Optional, Dict, Any
from kafka import KafkaProducer
from logger import Logger

class UserEventProducer:
    """Simple wrapper around kafka-python producer for user events"""

    def __init__(
        self,
        bootstrap_servers: Optional[str],
        topic: Optional[str],
        enabled: bool = True
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.enabled = enabled and bool(bootstrap_servers and topic)
        self._producer: Optional[KafkaProducer] = None
        self.logger = Logger.get_instance("UserEventProducer")
    
    def _get_or_create_producer(self) -> Optional[KafkaProducer]:
        """Lazy create a Kafka producer when configuration is provided"""
        if not self.enabled:
            return None
        
        if self._producer is None:
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                )
            except Exception as exc:
                self.enabled = False
                self.logger.error(f"Impossible d'initialiser KafkaProducer: {exc}", exc_info=True)
                return None
        return self._producer
    
    def publish(self, payload: Dict[str, Any]) -> None:
        """Publish an event payload, logging but not raising on failure"""
        producer = self._get_or_create_producer()
        if not producer:
            self.logger.debug(f"Kafka non configuré - événement ignoré: {payload.get('event')}")
            return
        
        try:
            producer.send(self.topic, value=payload)
        except Exception as exc:
            self.logger.error(f"Erreur lors de l'envoi de l'événement {payload.get('event')}: {exc}", exc_info=True)
    
    def close(self) -> None:
        """Close the underlying producer if it exists"""
        if self._producer:
            self._producer.flush()
            self._producer.close()
            self._producer = None
