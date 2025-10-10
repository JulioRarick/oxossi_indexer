import os
import sys
import json
import logging
import argparse
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.output_utils import format_and_output_json, export_to_elasticsearch_format
    from utils.data_utils import load_json_data
    
    # Importações opcionais para PDFs
    try:
        from utils.pdf_utils import extract_text_from_pdf
        PDF_SUPPORT = True
    except ImportError:
        PDF_SUPPORT = False
        logging.warning("PyMuPDF não encontrado. Processamento de PDFs desabilitado.")
    
    try:
        from extractors.names import extract_potential_names
        NAMES_SUPPORT = True
    except ImportError:
        NAMES_SUPPORT = False
        logging.warning("Extrator de nomes não disponível.")
    
    try:
        from extractors.dates import DateExtractor
        DATES_SUPPORT = True
    except ImportError:
        DATES_SUPPORT = False
        logging.warning("Extrator de datas não disponível.")
    
    try:
        from extractors.themes import ThemeAnalyzer
        THEMES_SUPPORT = True
    except ImportError:
        THEMES_SUPPORT = False
        logging.warning("Analisador de temas não disponível.")
    
    try:
        from extractors.places import PlaceExtractor
        PLACES_SUPPORT = True
    except ImportError:
        PLACES_SUPPORT = False
        logging.warning("Extrator de lugares não disponível.")
    
    try:
        from extractors.references import extract_references_with_anystyle
        REFERENCES_SUPPORT = True
    except ImportError:
        REFERENCES_SUPPORT = False
        logging.debug("Extrator de referências não disponível.")

except ImportError as e:
    logging.error(f"Erro crítico de importação: {e}")
    sys.exit(1)

DEFAULT_CONFIG = {
    "pdf_directory": "./pdfs",
    "backup_directory": "./backups",
    "config_directory": "./data",
    "output_directory": "./output"
}

class IndexerBackupManager:
    """Gerencia backups e recuperação do processo de indexação"""
    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.progress_file = self.backup_dir / f"progress_{self.session_id}.json"
        self.results_file = self.backup_dir / f"results_{self.session_id}.json"
        
    def save_progress(self, current_file: str, processed_files: List[str], 
                     failed_files: List[str], results: List[Dict[str, Any]]):
        """Salva progresso atual"""
        progress_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "current_file": current_file,
            "processed_files": processed_files,
            "failed_files": failed_files,
            "total_processed": len(processed_files),
            "total_failed": len(failed_files),
            "results_count": len(results)
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
            
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
            logging.debug(f"Progresso salvo: {len(processed_files)} processados, {len(failed_files)} falharam")
        except Exception as e:
            logging.error(f"Erro ao salvar progresso: {e}")
    
    def load_progress(self) -> Optional[Dict[str, Any]]:
        """Carrega progresso de sessão anterior"""
        try:
            # Procura pelo arquivo de progresso mais recente
            progress_files = list(self.backup_dir.glob("progress_*.json"))
            if not progress_files:
                return None
                
            latest_file = max(progress_files, key=lambda x: x.stat().st_mtime)
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            # Carrega resultados correspondentes
            results_file = self.backup_dir / f"results_{progress_data['session_id']}.json"
            if results_file.exists():
                with open(results_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                progress_data['results'] = results
            
            logging.info(f"Progresso carregado da sessão {progress_data['session_id']}")
            return progress_data
            
        except Exception as e:
            logging.error(f"Erro ao carregar progresso: {e}")
            return None
    
    def create_final_backup(self, final_results: Dict[str, Any]):
        """Cria backup final dos resultados"""
        backup_file = self.backup_dir / f"final_results_{self.session_id}.json"
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, indent=2, ensure_ascii=False)
            logging.info(f"Backup final salvo em: {backup_file}")
        except Exception as e:
            logging.error(f"Erro ao criar backup final: {e}")

class OxossiIndexer:
    """Indexador principal que processa PDFs ou dados JSON"""
    
    def __init__(self, config_dir: str = "./data", backup_dir: str = "./backups"):
        self.config_dir = Path(config_dir)
        self.backup_manager = IndexerBackupManager(backup_dir)
        self.results: List[Dict[str, Any]] = []
        self.processed_files: List[str] = []
        self.failed_files: List[str] = []
        
        self._load_configs()
    
    def _load_configs(self):
        """Carrega arquivos de configuração"""
        try:
            # Caminhos dos arquivos de configuração
            names_path = self.config_dir / "names.json"
            themes_path = self.config_dir / "themes.json"  
            dates_path = self.config_dir / "date_config.json"
            places_path = self.config_dir / "places.txt"
            
            # Carrega configurações usando os utilitários existentes
            self.names_config = load_json_data(str(names_path)) if names_path.exists() else {}
            self.themes_config = load_json_data(str(themes_path)) if themes_path.exists() else {}
            self.dates_config = load_json_data(str(dates_path)) if dates_path.exists() else {}
            
            # Carrega places se existir
            self.places_config = []
            if places_path.exists():
                with open(places_path, 'r', encoding='utf-8') as f:
                    self.places_config = [line.strip() for line in f if line.strip()]
            
            # Inicializa extractors se disponíveis
            self.date_extractor = DateExtractor(self.dates_config) if (DATES_SUPPORT and self.dates_config) else None
            self.theme_analyzer = ThemeAnalyzer(self.themes_config) if (THEMES_SUPPORT and self.themes_config) else None
            self.place_extractor = PlaceExtractor(self.places_config) if (PLACES_SUPPORT and self.places_config) else None
            
            logging.info("Configurações carregadas com sucesso")
            
        except Exception as e:
            logging.error(f"Erro ao carregar configurações: {e}")
            raise
    
    def process_pdf(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Processa um único arquivo PDF"""
        if not PDF_SUPPORT:
            logging.error("Processamento de PDF não disponível. Instale PyMuPDF: pip install PyMuPDF")
            return None
            
        try:
            text = extract_text_from_pdf(pdf_path)
            if not text:
                logging.warning(f"Não foi possível extrair texto de {pdf_path}")
                return None
            
            document = {
                "document_id": Path(pdf_path).stem,
                "filename": Path(pdf_path).name,
                "source_type": "pdf",
                "file_path": pdf_path,
                "processed_at": datetime.now().isoformat(),
                "text": text,
                "word_count": len(text.split()),
                "character_count": len(text)
            }
            
            if NAMES_SUPPORT and self.names_config:
                try:
                    names = extract_potential_names(
                        text,
                        first_names=self.names_config.get('first_names', []),
                        second_names=self.names_config.get('second_names', []),
                        prepositions=self.names_config.get('prepositions', [])
                    )
                    document["names_analysis"] = {
                        "potential_names_found": names,
                        "total_names": len(names)
                    }
                except Exception as e:
                    logging.error(f"Erro ao extrair nomes de {pdf_path}: {e}")
                    document["names_analysis"] = {"error": str(e)}
            
            if self.date_extractor:
                try:
                    dates_analysis = self.date_extractor.extract_and_analyze_dates(text)
                    temporal_context = self.date_extractor._analyze_temporal_context(text)
                    document["date_analysis"] = dates_analysis
                    document["temporal_analysis"] = temporal_context
                except Exception as e:
                    logging.error(f"Erro ao extrair datas de {pdf_path}: {e}")
                    document["date_analysis"] = {"error": str(e)}
            
            if self.theme_analyzer:
                try:
                    themes_analysis = self.theme_analyzer.analyze_text_themes(text)
                    document["themes_analysis"] = themes_analysis
                except Exception as e:
                    logging.error(f"Erro ao analisar temas de {pdf_path}: {e}")
                    document["themes_analysis"] = {"error": str(e)}
            
            if self.place_extractor:
                try:
                    places_analysis = self.place_extractor.extract_places(text)
                    document["places_analysis"] = places_analysis
                except Exception as e:
                    logging.error(f"Erro ao extrair lugares de {pdf_path}: {e}")
                    document["places_analysis"] = {"error": str(e)}
            
            if REFERENCES_SUPPORT:
                try:
                    references = extract_references_with_anystyle(pdf_path)
                    if references:
                        document["references_analysis"] = {
                            "raw_references": references,
                            "total_references": len(references)
                        }
                except Exception as e:
                    logging.debug(f"Anystyle não disponível ou erro ao extrair referências: {e}")
                    document["references_analysis"] = {"anystyle_available": False}
            
            return document
            
        except Exception as e:
            logging.error(f"Erro ao processar PDF {pdf_path}: {e}")
            return None
    
    def process_json_data(self, json_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Processa dados JSON (ex: itens scraped)"""
        processed_items = []
        
        for i, item in enumerate(json_data):
            try:
                document_id = item.get('_id', f"json_item_{i}")
                
                processed_item = {
                    "document_id": str(document_id),
                    "source_type": "json_data",
                    "processed_at": datetime.now().isoformat(),
                    "original_data": item,
                    **item  
                }
                
                text_content = (
                    item.get('text', '') or 
                    item.get('content', '') or 
                    item.get('texto_completo', '') or
                    item.get('description', '')
                )
                
                if text_content and isinstance(text_content, str):
                    processed_item["analyzed_text"] = text_content
                    processed_item["word_count"] = len(text_content.split())
                    
                    # Aplica análises se configurado
                    if self.date_extractor:
                        try:
                            dates_analysis = self.date_extractor.extract_and_analyze_dates(text_content)
                            temporal_context = self.date_extractor._analyze_temporal_context(text_content)
                            processed_item["date_analysis"] = dates_analysis
                            processed_item["temporal_analysis"] = temporal_context
                        except Exception as e:
                            logging.error(f"Erro ao analisar datas do item {document_id}: {e}")
                    
                    if self.theme_analyzer:
                        try:
                            themes_analysis = self.theme_analyzer.analyze_text_themes(text_content)
                            processed_item["themes_analysis"] = themes_analysis
                        except Exception as e:
                            logging.error(f"Erro ao analisar temas do item {document_id}: {e}")
                
                processed_items.append(processed_item)
                logging.info(f"Item JSON {document_id} processado com sucesso")
                
            except Exception as e:
                logging.error(f"Erro ao processar item JSON {i}: {e}")
                continue
        
        return processed_items
    
    def process_directory(self, directory: str, resume: bool = True) -> Dict[str, Any]:
        """Processa todos os PDFs em um diretório"""
        pdf_dir = Path(directory)
        
        if not pdf_dir.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory}")
        
        # Carrega progresso anterior se solicitado
        previous_progress = None
        if resume:
            previous_progress = self.backup_manager.load_progress()
            if previous_progress:
                self.processed_files = previous_progress.get('processed_files', [])
                self.failed_files = previous_progress.get('failed_files', [])
                self.results = previous_progress.get('results', [])
                logging.info(f"Resumindo processamento: {len(self.processed_files)} já processados")
        
        # Lista arquivos PDF
        pdf_files = list(pdf_dir.glob("*.pdf"))
        total_files = len(pdf_files)
        
        if total_files == 0:
            logging.warning(f"Nenhum arquivo PDF encontrado em {directory}")
        
        logging.info(f"Encontrados {total_files} arquivos PDF para processar.")
        
        # Processa arquivos
        for i, pdf_file in enumerate(pdf_files):
            filename = pdf_file.name
            
            # Pula se já foi processado
            if filename in self.processed_files:
                logging.info(f"Arquivo {filename} já processado, pulando...")
                continue
            
            logging.info(f"Processando [{i+1}/{total_files}]: {filename}")
            
            try:
                result = self.process_pdf(str(pdf_file))
                if result:
                    self.results.append(result)
                    self.processed_files.append(filename)
                    logging.info(f"✅ {filename} processado com sucesso")
                else:
                    self.failed_files.append(filename)
                    logging.warning(f"❌ Falha ao processar {filename}")
                
            except Exception as e:
                self.failed_files.append(filename)
                logging.error(f"❌ Erro ao processar {filename}: {e}")
            
            # Salva progresso a cada 5 arquivos
            if (i + 1) % 5 == 0:
                self.backup_manager.save_progress(
                    filename, self.processed_files, self.failed_files, self.results
                )
        
        # Salva progresso final
        self.backup_manager.save_progress(
            "COMPLETED", self.processed_files, self.failed_files, self.results
        )
        
        return self._generate_final_results()
    
    def process_json_file(self, json_file: str) -> Dict[str, Any]:
        """Processa arquivo JSON"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Garante que seja uma lista
            if not isinstance(json_data, list):
                json_data = [json_data]
            
            logging.info(f"Processando {len(json_data)} itens do arquivo JSON")
            
            processed_items = self.process_json_data(json_data)
            self.results.extend(processed_items)
            
            return self._generate_final_results()
            
        except Exception as e:
            logging.error(f"Erro ao processar arquivo JSON {json_file}: {e}")
            raise
    
    def _generate_final_results(self) -> Dict[str, Any]:
        """Gera relatório final dos resultados"""
        final_results = {
            "indexing_session": {
                "session_id": self.backup_manager.session_id,
                "completed_at": datetime.now().isoformat(),
                "total_processed": len(self.processed_files),
                "total_failed": len(self.failed_files),
                "total_results": len(self.results),
                "success_rate": len(self.processed_files) / (len(self.processed_files) + len(self.failed_files)) * 100 if (self.processed_files or self.failed_files) else 0
            },
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "results": self.results,
            "statistics": {
                "total_documents": len(self.results),
                "total_word_count": sum(r.get('word_count', 0) for r in self.results),
                "documents_with_dates": len([r for r in self.results if r.get('date_analysis', {}).get('count', 0) > 0]),
                "documents_with_names": len([r for r in self.results if r.get('names_analysis', {}).get('total_names', 0) > 0]),
                "documents_with_themes": len([r for r in self.results if r.get('themes_analysis', {}).get('total_keywords_found', 0) > 0])
            }
        }
        
        # Cria backup final
        self.backup_manager.create_final_backup(final_results)
        
        return final_results

def main():
    """Função principal com interface de linha de comando"""
    parser = argparse.ArgumentParser(
        description="Oxossi Indexer - Processa PDFs ou dados JSON e extrai informações históricas",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "input",
        help="Diretório com PDFs ou arquivo JSON para processar"
    )
    
    parser.add_argument(
        "--config-dir", "-c",
        default="./data",
        help="Diretório com arquivos de configuração"
    )
    
    parser.add_argument(
        "--backup-dir", "-b", 
        default="./backups",
        help="Diretório para salvar backups e progresso"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Arquivo de saída JSON (opcional)"
    )
    
    parser.add_argument(
        "--elasticsearch-format",
        action="store_true",
        help="Exporta também em formato otimizado para Elasticsearch"
    )
    
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Não resume processamento anterior (recomeça do zero)"
    )
    
    args = parser.parse_args()
    
    try:
        # Inicializa indexer
        indexer = OxossiIndexer(
            config_dir=args.config_dir,
            backup_dir=args.backup_dir
        )
        
        # Determina tipo de input
        input_path = Path(args.input)
        
        if input_path.is_file() and input_path.suffix.lower() == '.json':
            logging.info(f"Processando arquivo JSON: {input_path}")
            results = indexer.process_json_file(str(input_path))
        elif input_path.is_dir():
            if not PDF_SUPPORT:
                raise ValueError("Processamento de PDF não disponível. Instale PyMuPDF: pip install PyMuPDF")
            logging.info(f"Processando diretório de PDFs: {input_path}")
            results = indexer.process_directory(str(input_path), resume=not args.no_resume)
        else:
            raise ValueError(f"Input deve ser um diretório com PDFs ou arquivo JSON válido: {input_path}")
        
        # Exibe resultados em JSON
        format_and_output_json(
            results,
            status="Sucesso" if results['indexing_session']['total_processed'] > 0 else "Aviso",
            message=f"Processamento concluído. {results['indexing_session']['total_processed']} documentos processados.",
            output_file=args.output
        )
        
        # Exporta para Elasticsearch se solicitado
        if args.elasticsearch_format and results['results']:
            elasticsearch_file = args.output.replace('.json', '_elasticsearch.json') if args.output else "elasticsearch_export.json"
            export_to_elasticsearch_format(
                results['results'],
                output_file=elasticsearch_file
            )
        
        logging.info("🎉 Indexação concluída com sucesso!")
        
    except Exception as e:
        logging.error(f"💥 Erro durante indexação: {e}", exc_info=True)
        format_and_output_json(
            None,
            status="Erro",
            message=f"Falha durante indexação: {e}",
            output_file=args.output
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
