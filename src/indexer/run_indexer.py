
import os
import sys
import json
import logging
import argparse
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configuração de logging ANTES de qualquer uso
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger(__name__)  # IMPORTANTE: Definir log aqui

# Adiciona diretório pai ao path para importações
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from utils.output_utils import format_and_output_json, export_to_elasticsearch_format
    from utils.data_utils import load_json_data, validate_config_files, load_names_config
    
    # Importações opcionais para PDFs
    try:
        from utils.pdf_utils import extract_text_from_pdf
        PDF_SUPPORT = True
    except ImportError:
        PDF_SUPPORT = False
        log.warning("PyMuPDF não encontrado. Processamento de PDFs desabilitado.")
    
    try:
        from extractors.names import extract_potential_names
        NAMES_SUPPORT = True
    except ImportError:
        NAMES_SUPPORT = False
        log.warning("Extrator de nomes não disponível.")
    
    try:
        from extractors.dates import DateExtractor
        DATES_SUPPORT = True
    except ImportError:
        DATES_SUPPORT = False
        log.warning("Extrator de datas não disponível.")
    
    try:
        from extractors.themes import ThemeAnalyzer
        THEMES_SUPPORT = True
    except ImportError:
        THEMES_SUPPORT = False
        log.warning("Analisador de temas não disponível.")
    
    try:
        from extractors.places import PlaceExtractor
        PLACES_SUPPORT = True
    except ImportError:
        PLACES_SUPPORT = False
        log.warning("Extrator de lugares não disponível.")
    
    try:
        from extractors.references import ReferencesExtractor
        REFERENCES_SUPPORT = True
    except ImportError:
        REFERENCES_SUPPORT = False
        log.debug("Extrator de referências não disponível.")

    # Adicionando suporte para o novo extrator de pessoas
    try:
        from extractors.person_utils import PersonExtractor
        PERSON_SUPPORT = True
    except ImportError:
        PERSON_SUPPORT = False
        log.warning("Extrator de pessoas (person_utils) não disponível.")

    # Adicionando suporte para o extrator NER
    try:
        from extractors.ner_extractor import NerExtractor
        NER_SUPPORT = True
    except ImportError:
        NER_SUPPORT = False
        log.warning("Extrator NER (ner_extractor) não disponível.")

    # Adicionando suporte para o extrator de imagens
    try:
        from extractors.image_extractor import ImageExtractor
        IMAGES_SUPPORT = True
    except ImportError:
        IMAGES_SUPPORT = False
        log.warning("Extrator de imagens (image_extractor) não disponível.")

except ImportError as e:
    log.error(f"Erro crítico de importação: {e}")
    sys.exit(1)

DEFAULT_CONFIG = {
    "pdf_directory": "../pdf_pre_download",
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
                
            log.debug(f"Progresso salvo: {len(processed_files)} processados, {len(failed_files)} falharam")
        except Exception as e:
            log.error(f"Erro ao salvar progresso: {e}")
    
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
            
            log.info(f"Progresso carregado da sessão {progress_data['session_id']}")
            return progress_data
            
        except Exception as e:
            log.error(f"Erro ao carregar progresso: {e}")
            return None
    
    def create_final_backup(self, final_results: Dict[str, Any]):
        """Cria backup final dos resultados"""
        backup_file = self.backup_dir / f"final_results_{self.session_id}.json"
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, indent=2, ensure_ascii=False)
            log.info(f"Backup final salvo em: {backup_file}")
        except Exception as e:
            log.error(f"Erro ao criar backup final: {e}")

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
            # Garante que config_dir existe
            if not self.config_dir.exists():
                log.warning(f"Diretório de configuração não encontrado: {self.config_dir}")
                log.info("Criando diretório de configuração...")
                self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Valida arquivos de configuração primeiro
            log.info("Validando arquivos de configuração...")
            config_status = validate_config_files(self.config_dir)
            
            # Log do status
            for filename, is_valid in config_status.items():
                status = "✓ OK" if is_valid else "✗ Não disponível"
                log.info(f"  {filename}: {status}")
            
            # Caminhos dos arquivos de configuração
            names_path = self.config_dir / "names.json"
            themes_path = self.config_dir / "themes.json"  
            dates_path = self.config_dir / "date_config.json"
            places_path = self.config_dir / "places.txt"
            persons_path = self.config_dir / "persons.json"
            
            # Carrega configurações com fallback para dict/set vazio
            if names_path.exists() and names_path.stat().st_size > 0:
                first_names, second_names, prepositions = load_names_config(str(names_path))
                self.names_config = {
                    "first_names": list(first_names),
                    "second_names": list(second_names),
                    "prepositions": list(prepositions)
                }
            else:
                log.warning("Arquivo names.json não encontrado ou vazio. Usando configuração vazia.")
                self.names_config = {
                    "first_names": [],
                    "second_names": [],
                    "prepositions": ["de", "da", "do", "dos", "das"]
                }
            
            self.themes_config = load_json_data(str(themes_path)) if (themes_path.exists() and themes_path.stat().st_size > 0) else {}
            self.dates_config = load_json_data(str(dates_path)) if (dates_path.exists() and dates_path.stat().st_size > 0) else {}
            self.persons_config = load_json_data(str(persons_path)) if (persons_path.exists() and persons_path.stat().st_size > 0) else {}
            
            # Garante que são dicts (não None)
            self.names_config = self.names_config or {}
            self.themes_config = self.themes_config or {}
            self.dates_config = self.dates_config or {}
            self.persons_config = self.persons_config or {}
            
            # Inicializa extractors se disponíveis e com configuração válida
            self.date_extractor = (
                DateExtractor(self.dates_config) 
                if DATES_SUPPORT and self.dates_config 
                else None
            )
            
            self.theme_analyzer = (
                ThemeAnalyzer(self.themes_config) 
                if THEMES_SUPPORT and self.themes_config 
                else None
            )
            
            self.person_extractor = (
                PersonExtractor(self.persons_config) 
                if PERSON_SUPPORT and self.persons_config 
                else None
            )
            
            self.ner_extractor = NerExtractor() if NER_SUPPORT else None
            self.image_extractor = ImageExtractor() if IMAGES_SUPPORT else None
            
            # PlaceExtractor precisa de arquivo .txt
            if PLACES_SUPPORT and places_path.exists() and places_path.stat().st_size > 0:
                try:
                    self.place_extractor = PlaceExtractor(str(places_path))
                except Exception as e:
                    log.warning(f"Erro ao inicializar PlaceExtractor: {e}")
                    self.place_extractor = None
            else:
                self.place_extractor = None
                if PLACES_SUPPORT:
                    log.warning("PlaceExtractor desabilitado (arquivo places.txt não encontrado ou vazio)")
            
            # Referências
            if REFERENCES_SUPPORT:
                try:
                    self.references_extractor = ReferencesExtractor()
                except Exception as e:
                    log.warning(f"Erro ao inicializar ReferencesExtractor: {e}")
                    self.references_extractor = None
            else:
                self.references_extractor = None
            
            # Log resumo
            extractors_status = {
                'DateExtractor': self.date_extractor is not None,
                'ThemeAnalyzer': self.theme_analyzer is not None,
                'PersonExtractor': self.person_extractor is not None,
                'NerExtractor': self.ner_extractor is not None,
                'ImageExtractor': self.image_extractor is not None,
                'PlaceExtractor': self.place_extractor is not None,
                'ReferencesExtractor': self.references_extractor is not None
            }
            
            log.info("Status dos extractors:")
            for extractor, enabled in extractors_status.items():
                status = "✓ Ativo" if enabled else "✗ Inativo"
                log.info(f"  {extractor}: {status}")
            
            log.info("Configurações carregadas com sucesso")
        
        except Exception as e:
            log.error(f"Erro fatal ao carregar configurações: {e}", exc_info=True)
            raise
    
    # ... resto da classe permanece igual ...
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
            
            if self.ner_extractor:
                try:
                    ner_analysis = self.ner_extractor.extract_entities(text)
                    document["ner_analysis"] = ner_analysis
                except Exception as e:
                    logging.error(f"Erro na extração NER de {pdf_path}: {e}")
                    document["ner_analysis"] = {"error": str(e)}

            if self.person_extractor:
                try:
                    persons_analysis = self.person_extractor.extract_persons(text)
                    document["persons_analysis"] = persons_analysis
                except Exception as e:
                    logging.error(f"Erro ao extrair pessoas de {pdf_path}: {e}")
                    document["persons_analysis"] = {"error": str(e)}

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

            if self.image_extractor:
                try:
                    image_analysis = self.image_extractor.extract_images_from_pdf(pdf_path)
                    document["image_analysis"] = image_analysis
                except Exception as e:
                    logging.error(f"Erro ao extrair imagens de {pdf_path}: {e}")
                    document["image_analysis"] = {"error": str(e)}

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
                # 💡 CORREÇÃO APLICADA (mantida): Garante que o document_id é sempre uma string não vazia.
                document_id = str(item.get('_id', item.get('id', f"json_item_{self.backup_manager.session_id}_{i}")))
                
                processed_item = {
                    "document_id": document_id, 
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
                    
                    if self.date_extractor:
                        try:
                            dates_analysis = self.date_extractor.extract_and_analyze_dates(text_content)
                            temporal_context = self.date_extractor._analyze_temporal_context(text_content)
                            processed_item["date_analysis"] = dates_analysis
                            processed_item["temporal_analysis"] = temporal_context
                        except Exception as e:
                            logging.error(f"Erro ao analisar datas do item {document_id}: {e}")

                    if self.ner_extractor:
                        try:
                            ner_analysis = self.ner_extractor.extract_entities(text_content)
                            processed_item["ner_analysis"] = ner_analysis
                        except Exception as e:
                            logging.error(f"Erro na extração NER do item {document_id}: {e}")

                    if self.person_extractor:
                        try:
                            persons_analysis = self.person_extractor.extract_persons(text_content)
                            processed_item["persons_analysis"] = persons_analysis
                        except Exception as e:
                            logging.error(f"Erro ao analisar pessoas do item {document_id}: {e}")

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
        
        if resume:
            previous_progress = self.backup_manager.load_progress()
            if previous_progress:
                self.processed_files = previous_progress.get('processed_files', [])
                self.failed_files = previous_progress.get('failed_files', [])
                self.results = previous_progress.get('results', [])
                logging.info(f"Resumindo processamento: {len(self.processed_files)} já processados")
        
        pdf_files = list(pdf_dir.glob("*.pdf"))
        total_files = len(pdf_files)
        
        if total_files == 0:
            logging.warning(f"Nenhum arquivo PDF encontrado em {directory}")
        
        logging.info(f"Encontrados {total_files} arquivos PDF para processar.")
        
        for i, pdf_file in enumerate(pdf_files):
            filename = pdf_file.name
            
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
            
            if (i + 1) % 5 == 0:
                self.backup_manager.save_progress(
                    filename, self.processed_files, self.failed_files, self.results
                )
        
        self.backup_manager.save_progress(
            "COMPLETED", self.processed_files, self.failed_files, self.results
        )
        
        return self._generate_final_results()
    
    def process_json_file(self, json_file: str) -> Dict[str, Any]:
        """Processa arquivo JSON"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
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
        success_count = len(self.processed_files)
        total_attempts = success_count + len(self.failed_files)
        
        final_results = {
            "indexing_session": {
                "session_id": self.backup_manager.session_id,
                "completed_at": datetime.now().isoformat(),
                "total_processed": success_count,
                "total_failed": len(self.failed_files),
                "total_results": len(self.results),
                "success_rate": (success_count / total_attempts * 100) if total_attempts > 0 else 0
            },
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "results": self.results,
            "statistics": {
                "total_documents": len(self.results),
                "total_word_count": sum(r.get('word_count', 0) for r in self.results),
                "documents_with_dates": len([r for r in self.results if 'date_analysis' in r and not r['date_analysis'].get('error')]),
                "documents_with_names": len([r for r in self.results if 'names_analysis' in r and not r['names_analysis'].get('error')]),
                "documents_with_themes": len([r for r in self.results if 'themes_analysis' in r and not r['themes_analysis'].get('error')]),
                "documents_with_persons": len([r for r in self.results if 'persons_analysis' in r and not r['persons_analysis'].get('error')]),
                "documents_with_ner": len([r for r in self.results if 'ner_analysis' in r and not r['ner_analysis'].get('error')]),
                "documents_with_images": len([r for r in self.results if 'image_analysis' in r and not r['image_analysis'].get('error')])
            }
        }
        
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
        indexer = OxossiIndexer(
            config_dir=args.config_dir,
            backup_dir=args.backup_dir
        )
        
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
        
        format_and_output_json(
            results,
            status="Sucesso" if results['indexing_session']['total_processed'] > 0 else "Aviso",
            message=f"Processamento concluído. {results['indexing_session']['total_processed']} documentos processados.",
            output_file=args.output
        )
        
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
