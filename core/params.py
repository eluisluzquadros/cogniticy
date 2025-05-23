# cogniticy/core/params.py

import yaml
from typing import Dict, Any, Optional, List
import os
import copy # Para deepcopy dos dicionários de parâmetros
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")

class AppParams:
    """
    Gerencia os parâmetros da aplicação, carregando de um arquivo YAML padrão
    e permitindo a fusão com parâmetros específicos do lote.
    """

    def __init__(self, default_config_path: str = DEFAULT_CONFIG_PATH):
        self.default_config_path = default_config_path
        self.base_params: Dict[str, Any] = self._load_yaml_config(self.default_config_path)
        if not self.base_params:
            logger.error(f"Não foi possível carregar os parâmetros base de {self.default_config_path}. Usando dicionário vazio.")
            self.base_params = {}
        self.current_params: Dict[str, Any] = copy.deepcopy(self.base_params)

    def _load_yaml_config(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Arquivo de configuração não encontrado em {file_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Erro ao parsear o arquivo YAML {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Ocorreu um erro inesperado ao carregar {file_path}: {e}")
            return {}

    def _merge_params(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_params(merged[key], value)
            else:
                merged[key] = value
        return merged

    def update_for_lot(self, lot_specific_params: Dict[str, Any]) -> None:
        base_for_merge = copy.deepcopy(self.base_params)
        self.current_params = self._merge_params(base_for_merge, lot_specific_params)
        logger.debug(f"Parâmetros atualizados para o lote (numlote: {self.zoning.get('numlote', 'N/A')}): {self.current_params}")


    def get_param(self, param_path: str, default: Optional[Any] = None) -> Any:
        keys = param_path.split('.')
        value = self.current_params
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                else:
                    logger.debug(f"Caminho de parâmetro '{param_path}' inválido em '{key}'.")
                    return default
            return value
        except KeyError:
            logger.debug(f"Parâmetro '{param_path}' não encontrado. Retornando default: {default}")
            return default
        except Exception as e:
            logger.error(f"Erro ao acessar parâmetro '{param_path}': {e}")
            return default

    def get_all_params(self) -> Dict[str, Any]:
        return copy.deepcopy(self.current_params)

    @property
    def zoning(self) -> Dict[str, Any]:
        return self.current_params.get("zoning_parameters", {})

    @property
    def normative(self) -> Dict[str, Any]:
        return self.current_params.get("normative_parameters", {})

    @property
    def architectural(self) -> Dict[str, Any]:
        return self.current_params.get("architectural_parameters", {})

    @property
    def parking(self) -> Dict[str, Any]:
        return self.current_params.get("parking_parameters", {})

    @property
    def modeling_strategy(self) -> Dict[str, Any]:
        return self.current_params.get("modeling_strategy", {})

    @property
    def simulation(self) -> Dict[str, Any]:
        return self.current_params.get("simulation_parameters", {})

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..")) 
    config_path_for_test = os.path.join(project_root, "config", "default.yaml")

    if not os.path.exists(config_path_for_test):
        logger.error(f"Arquivo de configuração de teste não encontrado em {config_path_for_test}")
    else:
        params_manager = AppParams(default_config_path=config_path_for_test)
        logger.info(f"Altura máxima padrão: {params_manager.get_param('normative_parameters.max_height')}")
        
        lot_data = {
            "normative_parameters": {"max_height": 50.0, "max_far": 1.5},
            "zoning_parameters": {"numlote": "LOTE_XYZ_789"}
        }
        params_manager.update_for_lot(lot_data)
        logger.info(f"Altura máxima do lote: {params_manager.normative.get('max_height')}")
        logger.info(f"Número do lote: {params_manager.zoning.get('numlote')}")

