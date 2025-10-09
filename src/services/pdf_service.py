# Serviço para processamento de PDFs
from utils.pdf_utils import extract_text_from_pdf
from src.extractors.names import extract_potential_names
from src.extractors.dates import load_date_config
from src.extractors.themes import analyze_text_themes

class PDFService:
    def __init__(self, names_config, themes_config):
        self.names_config = names_config
        self.themes_config = themes_config

    def process_pdf(self, file_path: str):
        text = extract_text_from_pdf(file_path)
        if not text:
            return None

        names = extract_potential_names(
            text,
            first_names=self.names_config[0],
            second_names=self.names_config[1],
            prepositions=self.names_config[2]
        )
        themes = analyze_text_themes(
            text,
            config=self.themes_config
        )
        return {
            "text": text,
            "names": names,
            "themes": themes
        }
