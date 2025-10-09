from utils.data_utils import load_names_config, load_themes_config

class ConfigFactory:
    @staticmethod
    def load_names_config(file_path: str):
        return load_names_config(file_path)

    @staticmethod
    def load_themes_config(file_path: str):
        return load_themes_config(file_path)
