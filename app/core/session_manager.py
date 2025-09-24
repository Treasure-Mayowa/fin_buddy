import json
import datetime
import os
from typing import Dict, Any
import logging
import redis

SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))  # 1 hour

class SessionManager:
    def __init__(self, redis_client: redis.Redis, active_sessions):
        self.redis = redis_client
        self.active_sessions = active_sessions
        self.logger = logging.getLogger(__name__)
    
    # Get user session details
    def get_session(self, user_id: str) -> Dict[str, Any]:
        key = f"session:{user_id}"
        data = self.redis.get(key)
        if data:
            session = json.loads(data)
            self._update_active_sessions()
            return session
        
        # Create new session
        session = {
            "stage": "idle",
            "message_history": [],
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        self.save_session(user_id, session)
        return session
    
    # Save session for up to session time limit
    def save_session(self, user_id: str, session: Dict[str, Any]) -> None:
        key = f"session:{user_id}"
        session["last_activity"] = datetime.utcnow().isoformat()
        self.redis.setex(key, SESSION_TTL, json.dumps(session))
        self._update_active_sessions()

    # Add message to user session history
    def add_message(self, user_id: str, message: Dict[str, Any]):
        session = self.get_session(user_id)
        session["message_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        })
        
        # Keep only last 5 messages to conserve memory and input tokens
        if len(session["message_history"]) > 5:
            session["message_history"] = session["message_history"][-5:]
        
        self.save_session(user_id, session)
    
    # Change user session stage
    def set_stage(self, user_id: str, stage: str):
       session = self.get_session(user_id)
       session["stage"] = stage
       self.save_session(user_id, session)

    def get_message_history(self, user_id: str, limit: int = 10) -> list:
        try:
            session = self.get_session(user_id)
            history = session.get("message_history", [])
            return history[-limit:] if limit else history
        except Exception as e:
            self.logger.error(f"Error getting message history for {user_id}: {e}")
            return []

    # Update active user  sessions
    def _update_active_sessions(self):
        try:
            keys = self.redis.keys("session:*")
            self.active_sessions.set(len(keys))
        except Exception as e:
            self.logger.error(f"Failed to update active sessions gauge: {e}")
