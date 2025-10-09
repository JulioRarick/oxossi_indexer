import os
import sys
import logging
from pymongo.database import Database
from pymongo.errors import PyMongoError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.utils.mongo_connection import get_db_connection, close_db_connection
    from src.utils.pdf_utils import extract_text_from_pdf
    from src.extractors.names import extract_names
    from src.extractors.dates import extract_dates
    from src.extractors.themes import analyze_text_themes
    from src.repositories.mongo_repository import MongoRepository
    from src.services.pdf_service import PDFService
    from src.factories.config_factory import ConfigFactory
except ImportError as e:
    logging.error(f"Erro de importação. Verifique se todos os módulos estão no lugar correto: {e}")
    sys.exit(1)

PDF_DIRECTORY = "/app/src/pdfs"

def process_and_index_pdfs(db: Database):
    """
    Processa todos os arquivos PDF em um diretório, extrai informações
    e os insere ou atualiza no MongoDB de forma segura.
    """
    if not os.path.exists(PDF_DIRECTORY):
        logging.error(f"Diretório de PDFs não encontrado: {PDF_DIRECTORY}")
        return

    collection = db.documents
    pdf_files = [f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith(".pdf")]
    total_files = len(pdf_files)
    logging.info(f"Encontrados {total_files} arquivos PDF para processar.")
    
    names_config = ConfigFactory.load_names_config("/app/src/data/names.json")
    themes_config = ConfigFactory.load_themes_config("/app/src/data/themes.json")
    dates_config = ConfigFactory.load_json_data("/app/src/data/date_config.json")

    pdf_service = PDFService(names_config, themes_config, dates_config)
    mongo_repo = MongoRepository(db)

    for i, filename in enumerate(pdf_files):
        file_path = os.path.join(PDF_DIRECTORY, filename)
        document_id = os.path.splitext(filename)[0]

        try:
            result = pdf_service.process_pdf(file_path)
            if result:
                document = {
                    "_id": document_id,
                    "filename": filename,
                    **result,
                    "path": file_path
                }
                mongo_repo.insert_document("documents", document)
                logging.info(f"Documento '{filename}' indexado com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao processar documento '{filename}': {e}")

def process_scraped_items(db: Database):
    """
    Processa os documentos da coleção scraped_items e os insere na coleção documents.
    """
    scraped_items = db.scraped_items.find()
    collection = db.documents

    for item in scraped_items:
        document_id = str(item.get("_id"))

        try:
            document = {
                "_id": document_id,
                "title": item.get("title"),
                "author": item.get("author"),
                "content": item.get("content"),
                "date": item.get("date"),
            }
            collection.insert_one(document)
            logging.info(f"Documento '{document_id}' adicionado com sucesso à coleção documents.")
        except Exception as e:
            logging.error(f"Erro ao processar documento '{document_id}': {e}")

if __name__ == "__main__":
    db_conn = None
    try:
        logging.info("Iniciando processo de indexação...")
        db_conn = get_db_connection()

        if db_conn is None:
            logging.error("Conexão com o MongoDB não foi estabelecida. Encerrando o indexador.")
            sys.exit(1)

        process_scraped_items(db_conn)  
        process_and_index_pdfs(db_conn) 
        logging.info("Processo de indexação concluído.")
    except PyMongoError as e:
        logging.critical(f"Erro fatal de conexão com o MongoDB. O script não pode continuar. Erro: {e}")
    except Exception as e:
        logging.critical(f"Um erro crítico inesperado ocorreu: {e}", exc_info=True)
    finally:
        if db_conn is not None:
            close_db_connection()
            logging.info("Conexão com o MongoDB fechada.")
