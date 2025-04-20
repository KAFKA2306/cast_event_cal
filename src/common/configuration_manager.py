# src/common/configuration_manager.py
import yaml

class ConfigurationManager:
    def __init__(self, config_file_path):
        self.config = self._load_config(config_file_path)

    def _load_config(self, config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_file_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing configuration file: {config_file_path} - {e}")

    def get_config(self):
        return self.config
