import json
import argparse
import logging
import os
import sys
from collections import Counter
from typing import Optional, List, Dict, Any, Union

from utils.pdf_utils import extract_text_from_pdf
from utils.data_utils import load_themes_config
from utils.output_utils import format_and_output_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__)


class ThemeAnalyzer:
    def __init__(self, config: Optional[Union[str, Dict[str, List[str]]]]):
        if isinstance(config, str):
            self.config = load_themes_config(config)
        elif isinstance(config, dict):
            self.config = config
        else:
            raise ValueError("Configuração inválida para ThemeAnalyzer. Deve ser um caminho de arquivo ou um dicionário.")

    def analyze_text_themes(self, text: str) -> Dict[str, Any]:
        results_template: Dict[str, Any] = {
            "theme_counts": {},
            "keyword_counts": {},
            "top_theme": None,
            "theme_percentages": {},
            "total_keywords_found": 0
        }

        if not text:
            log.warning("Texto de entrada vazio para análise de temas.")
            return results_template
        if not self.config:
            log.warning("Grupos de temas vazios para análise.")
            return results_template

        words_in_text = text.lower().split()
        text_word_counts = Counter(words_in_text)

        theme_counts: Dict[str, int] = {theme: 0 for theme in self.config}
        keyword_counts: Dict[str, int] = {}
        all_keywords_found_count = 0

        log.info("Contando ocorrências de palavras-chave por tema...")
        for theme, keywords in self.config.items():
            theme_total = 0
            for keyword in keywords:
                kw_lower = keyword.lower().strip()
                if not kw_lower: continue 

                count = text_word_counts.get(kw_lower, 0)
                if count > 0:
                    keyword_counts[kw_lower] = count
                    theme_total += count
                    all_keywords_found_count += count
            theme_counts[theme] = theme_total

        results_template["theme_counts"] = theme_counts
        results_template["keyword_counts"] = keyword_counts
        results_template["total_keywords_found"] = all_keywords_found_count

        if all_keywords_found_count == 0:
            log.info("Nenhuma palavra-chave de tema encontrada no texto.")
            return results_template

        theme_percentages: Dict[str, float] = {}
        top_theme: Optional[Union[str, List[str]]] = None
        max_count = 0

        positive_theme_counts = {theme: count for theme, count in theme_counts.items() if count > 0}

        if positive_theme_counts:
             max_count = max(positive_theme_counts.values())
             tied_top_themes = [theme for theme, count in positive_theme_counts.items() if count == max_count]
             if len(tied_top_themes) == 1:
                 top_theme = tied_top_themes[0]
             else:
                 top_theme = sorted(tied_top_themes) 

        for theme, count in theme_counts.items():
            percentage = (count / all_keywords_found_count) * 100 if all_keywords_found_count > 0 else 0
            theme_percentages[theme] = round(percentage, 2) 

        results_template["top_theme"] = top_theme
        results_template["theme_percentages"] = theme_percentages

        log.info(f"Análise de temas concluída. Tema principal: {top_theme or 'N/A'}")
        return results_template


def analyze_text_themes(text: str, config: Dict[str, List[str]]) -> Dict[str, Any]:
    extractor = ThemeAnalyzer(config)
    return extractor.analyze_text_themes(text)


def main():
    parser = argparse.ArgumentParser(
        description="Analisa a frequência de temas em um arquivo TXT ou PDF com base em palavras-chave definidas em um JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Caminho para o arquivo de entrada (.txt ou .pdf)."
    )
    parser.add_argument(
        "--themes-config", "-t",
        default="../data/themes.json", 
        help="Caminho para o arquivo JSON de configuração de temas."
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Caminho opcional para salvar a saída JSON."
    )
    args = parser.parse_args()

    log.info(f"Iniciando análise de temas para: {args.input_file}")
    log.info(f"Usando arquivo de temas: {args.themes_config}")
    if args.output:
        log.info(f"Saída JSON será salva em: {args.output}")

    analyzer = ThemeAnalyzer(args.themes_config)

    file_text: Optional[str] = None
    input_path = args.input_file
    
    if not os.path.exists(input_path):
        error_msg = f"Erro: Arquivo de entrada não encontrado em '{input_path}'"
        log.error(error_msg)
        format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
        sys.exit(1)
    elif input_path.lower().endswith(".pdf"):
        file_text = extract_text_from_pdf(input_path)
        if file_text is None:
            error_msg = f"Falha ao extrair texto do PDF '{input_path}'."
            format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
            sys.exit(1)
    elif input_path.lower().endswith(".txt"):
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                file_text = f.read()
            log.info(f"Texto lido com sucesso de '{input_path}'")
        except Exception as e:
            error_msg = f"Erro ao ler arquivo de texto '{input_path}': {e}"
            log.error(error_msg, exc_info=True)
            format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
            sys.exit(1)
    else:
        error_msg = f"Erro: Tipo de arquivo de entrada não suportado para '{input_path}'. Forneça .txt ou .pdf."
        log.error(error_msg)
        format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
        sys.exit(1)

    analysis_results = analyzer.analyze_text_themes(file_text)

    status = "Sucesso" if analysis_results.get("total_keywords_found", 0) > 0 else "Aviso"
    message = "Análise de temas concluída." if status == "Sucesso" else "Nenhuma palavra-chave de tema encontrada no texto."

    format_and_output_json(analysis_results, status=status, message=message, output_file=args.output)

    log.info("Processo concluído.")


if __name__ == "__main__":
    main()
