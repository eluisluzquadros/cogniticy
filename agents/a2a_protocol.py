from dataclasses import dataclass
from typing import Dict, Any, Optional
import uuid
import datetime

@dataclass
class A2AMessage:
    """
    Estrutura de mensagem para comunicação entre agentes seguindo o protocolo A2A.
    """
    sender: str
    receiver: str
    performative: str  # ex: 'propose', 'inform', 'request', 'confirm'
    content: Dict[str, Any]
    conversation_id: Optional[str] = None
    message_id: str = uuid.uuid4().hex
    timestamp: str = datetime.datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "performative": self.performative,
            "content": self.content,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'A2AMessage':
        return A2AMessage(
            sender=data["sender"],
            receiver=data["receiver"],
            performative=data["performative"],
            content=data["content"],
            conversation_id=data.get("conversation_id"),
            message_id=data.get("message_id", uuid.uuid4().hex),
            timestamp=data.get("timestamp", datetime.datetime.utcnow().isoformat()),
        )
