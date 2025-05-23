"""
Módulo io/checkpoint.py
Este módulo contém a classe CheckpointManager que é responsável por
gerenciar checkpoints e recuperação de falhas durante o processamento.
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)

class CheckpointManager:
    """
    Gerencia checkpoints durante o processamento de lotes para permitir
    recuperação em caso de falhas.
    """
    
    def __init__(self, output_dir: str = "checkpoints", prefix: str = "morphomax_checkpoint"):
        """
        Inicializa o gerenciador de checkpoints.
        
        Args:
            output_dir: Diretório para salvar os checkpoints
            prefix: Prefixo para os arquivos de checkpoint
        """
        self.output_dir = output_dir
        self.prefix = prefix
        
        # Criar diretório de saída
        os.makedirs(output_dir, exist_ok=True)
        
        # Estado atual
        self.processed_lots = set()
        self.failed_lots = {}
        self.results = {}
        
        # Metadata
        self.start_time = time.time()
        self.last_checkpoint_time = None
        self.checkpoint_count = 0
    
    def record_processed_lot(self, lot_id: str, result: Dict) -> None:
        """
        Registra um lote processado com sucesso.
        
        Args:
            lot_id: ID do lote processado
            result: Resultado do processamento
        """
        self.processed_lots.add(lot_id)
        self.results[lot_id] = result
    
    def record_failed_lot(self, lot_id: str, error: str) -> None:
        """
        Registra um lote que falhou no processamento.
        
        Args:
            lot_id: ID do lote que falhou
            error: Mensagem de erro
        """
        self.failed_lots[lot_id] = error
    
    def save_checkpoint(self, additional_data: Optional[Dict] = None) -> str:
        """
        Salva o estado atual como um checkpoint.
        
        Args:
            additional_data: Dados adicionais a serem incluídos no checkpoint
            
        Returns:
            Caminho para o arquivo de checkpoint
        """
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        # Nome do arquivo de checkpoint
        checkpoint_file = os.path.join(
            self.output_dir, 
            f"{self.prefix}_{timestamp}.json"
        )
        
        # Preparar dados do checkpoint
        checkpoint_data = {
            "timestamp": timestamp,
            "datetime": now.isoformat(),
            "processed_lots": list(self.processed_lots),
            "failed_lots": self.failed_lots,
            "results": self.results,
            "metadata": {
                "start_time": self.start_time,
                "elapsed_seconds": time.time() - self.start_time,
                "checkpoint_count": self.checkpoint_count + 1
            }
        }
        
        # Adicionar dados extras se fornecidos
        if additional_data:
            checkpoint_data["additional_data"] = additional_data
        
        # Salvar arquivo de checkpoint
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        # Atualizar estado
        self.last_checkpoint_time = time.time()
        self.checkpoint_count += 1
        
        logger.info(f"Checkpoint salvo em {checkpoint_file} - {len(self.processed_lots)} lotes processados")
        
        return checkpoint_file
    
    def load_checkpoint(self, checkpoint_file: str) -> Dict:
        """
        Carrega um checkpoint de um arquivo.
        
        Args:
            checkpoint_file: Caminho para o arquivo de checkpoint
            
        Returns:
            Dados do checkpoint
        """
        logger.info(f"Carregando checkpoint de {checkpoint_file}")
        
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            # Restaurar estado
            self.processed_lots = set(checkpoint_data.get("processed_lots", []))
            self.failed_lots = checkpoint_data.get("failed_lots", {})
            self.results = checkpoint_data.get("results", {})
            
            # Restaurar metadata
            metadata = checkpoint_data.get("metadata", {})
            self.start_time = metadata.get("start_time", time.time())
            self.checkpoint_count = metadata.get("checkpoint_count", 0)
            
            logger.info(f"Checkpoint carregado: {len(self.processed_lots)} lotes processados anteriormente")
            
            return checkpoint_data
            
        except Exception as e:
            logger.error(f"Erro ao carregar checkpoint: {e}")
            return {}
    
    def get_latest_checkpoint(self) -> Optional[str]:
        """
        Retorna o caminho para o checkpoint mais recente.
        
        Returns:
            Caminho para o arquivo de checkpoint mais recente, ou None se não houver
        """
        try:
            # Listar arquivos de checkpoint
            checkpoint_files = [
                os.path.join(self.output_dir, f) 
                for f in os.listdir(self.output_dir) 
                if f.startswith(self.prefix) and f.endswith('.json')
            ]
            
            if not checkpoint_files:
                return None
            
            # Ordenar por data de modificação
            checkpoint_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            return checkpoint_files[0]
            
        except Exception as e:
            logger.error(f"Erro ao buscar checkpoints: {e}")
            return None
    
    def should_create_checkpoint(self, 
                               processed_count: int, 
                               interval: int = 50, 
                               time_interval: int = 300) -> bool:
        """
        Verifica se é hora de criar um novo checkpoint.
        
        Args:
            processed_count: Número de lotes processados desde o último checkpoint
            interval: Intervalo em número de lotes para criar checkpoint
            time_interval: Intervalo em segundos para criar checkpoint
            
        Returns:
            True se deve criar checkpoint, False caso contrário
        """
        # Sempre criar checkpoint após um certo número de lotes
        if processed_count >= interval:
            return True
        
        # Criar checkpoint após um certo tempo
        if self.last_checkpoint_time is None:
            # Primeiro checkpoint após início
            return processed_count > 0
        elif time.time() - self.last_checkpoint_time >= time_interval:
            # Intervalo de tempo atingido
            return processed_count > 0
        
        return False
    
    def get_pending_lots(self, all_lots: List[str]) -> List[str]:
        """
        Retorna a lista de lotes ainda não processados.
        
        Args:
            all_lots: Lista de todos os lotes a serem processados
            
        Returns:
            Lista de lotes pendentes
        """
        processed = self.processed_lots.union(set(self.failed_lots.keys()))
        pending = [lot_id for lot_id in all_lots if lot_id not in processed]
        
        return pending
    
    def get_processing_stats(self) -> Dict:
        """
        Retorna estatísticas do processamento atual.
        
        Returns:
            Dicionário com estatísticas
        """
        now = time.time()
        elapsed = now - self.start_time
        
        # Cálculo de taxa de processamento
        processed_count = len(self.processed_lots)
        failed_count = len(self.failed_lots)
        total_processed = processed_count + failed_count
        
        # Evitar divisão por zero
        rate = total_processed / elapsed if elapsed > 0 else 0
        
        return {
            "processed_count": processed_count,
            "failed_count": failed_count,
            "total_processed": total_processed,
            "elapsed_seconds": elapsed,
            "elapsed_formatted": self._format_time(elapsed),
            "processing_rate": rate,  # lotes por segundo
            "estimated_time_per_lot": 1 / rate if rate > 0 else 0,
            "checkpoint_count": self.checkpoint_count
        }
    
    def _format_time(self, seconds: float) -> str:
        """
        Formata um tempo em segundos para uma string legível.
        
        Args:
            seconds: Tempo em segundos
            
        Returns:
            Tempo formatado (HH:MM:SS)
        """
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def estimate_remaining_time(self, pending_lots_count: int) -> str:
        """
        Estima o tempo restante para processar os lotes pendentes.
        
        Args:
            pending_lots_count: Número de lotes pendentes
            
        Returns:
            Tempo estimado formatado
        """
        stats = self.get_processing_stats()
        
        if stats["processing_rate"] > 0:
            remaining_seconds = pending_lots_count / stats["processing_rate"]
            return self._format_time(remaining_seconds)
        else:
            return "Desconhecido"
    
    def generate_report(self, all_lots: List[str], include_results: bool = False) -> Dict:
        """
        Gera um relatório completo do processamento.
        
        Args:
            all_lots: Lista de todos os lotes a serem processados
            include_results: Se True, inclui resultados detalhados no relatório
            
        Returns:
            Dicionário com relatório completo
        """
        # Obter estatísticas atuais
        stats = self.get_processing_stats()
        
        # Calcular lotes pendentes
        pending_lots = self.get_pending_lots(all_lots)
        pending_count = len(pending_lots)
        
        # Preparar relatório
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_lots": len(all_lots),
            "processed_lots": len(self.processed_lots),
            "failed_lots": len(self.failed_lots),
            "pending_lots": pending_count,
            "progress_percent": (stats["total_processed"] / len(all_lots) * 100) if all_lots else 0,
            "elapsed_time": stats["elapsed_formatted"],
            "estimated_remaining": self.estimate_remaining_time(pending_count),
            "processing_rate": stats["processing_rate"],
            "checkpoint_count": stats["checkpoint_count"]
        }
        
        # Incluir lista de falhas
        if self.failed_lots:
            report["failures"] = self.failed_lots
        
        # Incluir resultados detalhados se solicitado
        if include_results:
            report["detailed_results"] = self.results
        
        return report
