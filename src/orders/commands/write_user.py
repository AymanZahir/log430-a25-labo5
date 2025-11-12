"""
Users (write-only model)
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

from datetime import datetime, timezone
from typing import Dict, Any

import config
from logger import Logger
from orders.models.user import User
from db import get_sqlalchemy_session
from events.user_event_producer import UserEventProducer

logger = Logger.get_instance("WriteUser")
event_producer = UserEventProducer(
    bootstrap_servers=config.KAFKA_HOST,
    topic=config.KAFKA_TOPIC,
    enabled=config.KAFKA_ENABLED
)

def _now_iso() -> str:
    """Return current UTC timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()

def _user_snapshot(user: User) -> Dict[str, Any]:
    """Extract relevant user fields for events"""
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "user_type_id": getattr(user, "user_type_id", None),
    }

def _publish_user_event(event_type: str, user_data: Dict[str, Any], extra: Dict[str, Any] | None = None) -> None:
    """Send user-related events to Kafka"""
    payload = {
        "event": event_type,
        "datetime": _now_iso(),
        **{k: v for k, v in user_data.items() if v is not None}
    }

    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})

    event_producer.publish(payload)

def add_user(name: str, email: str, user_type_id: int | None = None):
    """Insert user with items in MySQL and emit UserCreated event"""
    if not name or not email:
        raise ValueError("Cannot create user. A user must have name and email.")

    if user_type_id is None:
        user_type_id = 1
    
    try:
        user_type_id = int(user_type_id)
    except (TypeError, ValueError):
        raise ValueError("Cannot create user. Invalid user_type_id.")
    
    if user_type_id <= 0:
        raise ValueError("Cannot create user. user_type_id must be positive.")
    
    session = get_sqlalchemy_session()

    try: 
        new_user = User(name=name, email=email, user_type_id=user_type_id)
        session.add(new_user)
        session.flush() 
        session.commit()

        _publish_user_event("UserCreated", _user_snapshot(new_user))
        logger.debug(f"Utilisateur créé (ID: {new_user.id}) et événement publié.")
        return new_user.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def delete_user(user_id: int):
    """Delete user in MySQL and emit UserDeleted event"""
    session = get_sqlalchemy_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            snapshot = _user_snapshot(user)
            session.delete(user)
            session.commit()

            _publish_user_event("UserDeleted", snapshot, {"deletion_date": _now_iso()})
            logger.debug(f"Utilisateur supprimé (ID: {user_id}) et événement publié.")
            return 1  
        else:
            return 0  
            
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
