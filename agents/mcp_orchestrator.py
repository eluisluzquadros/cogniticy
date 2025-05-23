from agents.a2a_protocol import A2AMessage
from agents.shape_agent import ShapeAgent
from shapely.geometry import Polygon
from typing import List
import uuid

class MCPOrchestrator:
    """
    Coordena múltiplos agentes via protocolo A2A.
    Responsável por enviar tarefas, aguardar respostas e integrar resultados.
    """
    def __init__(self, agent_registry: List[ShapeAgent]):
        self.agents = {agent.agent_id: agent for agent in agent_registry}

    def broadcast_refinement(self, geometry: Polygon) -> List[Polygon]:
        """
        Envia a mesma geometria para todos os agentes e coleta as versões refinadas.
        """
        conversation_id = uuid.uuid4().hex
        responses = []

        for agent_id, agent in self.agents.items():
            msg = A2AMessage(
                sender="orchestrator",
                receiver=agent_id,
                performative="request",
                content={"action": "refine_geometry", "geometry": geometry},
                conversation_id=conversation_id
            )
            response = agent.receive(msg)
            if response.performative == "inform" and "refined_geometry" in response.content:
                responses.append(response.content["refined_geometry"])

        return responses