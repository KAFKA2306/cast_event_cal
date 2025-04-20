import yaml

import yaml

import yaml
import importlib

class ConfigurationManager:
    def __init__(self, main_config_file, scraping_targets_file="config/scraping_targets.yaml", data_schemas_file="models/data_schemas.py"):
        self.main_config_file = main_config_file
        self.scraping_targets_file = scraping_targets_file
        self.data_schemas_file = data_schemas_file
        self.config = self.load_config()

    def load_config(self):
        config = {}
        with open(self.main_config_file, 'r') as f:
            main_config = yaml.safe_load(f)
            config.update(main_config)

        with open(self.scraping_targets_file, 'r', encoding='utf-8') as f:
            scraping_targets = yaml.safe_load(f)
            config['scraping_targets'] = scraping_targets

        # Load data schemas from Python file
        spec = importlib.util.spec_from_file_location("data_schemas", self.data_schemas_file)
        data_schemas = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_schemas)
        config['data_schemas'] = data_schemas.event_schema

        return config

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def save_config(self):
        with open(self.main_config_file, 'w') as f:
            yaml.dump(self.config, f, indent=4)