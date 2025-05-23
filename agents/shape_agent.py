from shapely.geometry import Polygon
from agents.a2a_protocol import A2AMessage
from core.geometry_utils import compact_geometry

class ShapeAgent:
    """
    Agente responsável por propor ou refinar formas morfológicas com base em mensagens A2A.
    """
    def __init__(self, agent_id: str, compacity_factor: float = 0.95):
        self.agent_id = agent_id
        self.compacity_factor = compacity_factor

    def receive(self, message: A2AMessage) -> A2AMessage:
        """
        Processa uma mensagem e retorna uma resposta conforme o tipo de interação.
        """
        if message.performative == "request" and message.content.get("action") == "refine_geometry":
            input_geom = message.content.get("geometry")
            if isinstance(input_geom, Polygon):
                refined = compact_geometry(input_geom, self.compacity_factor)
                return A2AMessage(
                    sender=self.agent_id,
                    receiver=message.sender,
                    performative="inform",
                    content={"refined_geometry": refined},
                    conversation_id=message.conversation_id
                )

        return A2AMessage(
            sender=self.agent_id,
            receiver=message.sender,
            performative="not-understood",
            content={},
            conversation_id=message.conversation_id
        )
