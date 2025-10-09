import sys
import os
from pymongo.database import Database
from pymongo.errors import ConnectionFailure
import pathlib
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.utils.mongo_connection import get_db_connection

def get_db() -> Database:
    """
    Dependência do FastAPI para obter uma conexão com o banco de dados.
    Verifica a conexão antes de retorná-la.
    """
    try:
        db = get_db_connection()
        db.client.admin.command('ping')
        return db
    except ConnectionFailure as e:
        print(f"Erro ao conectar com o MongoDB: {e}")
        raise RuntimeError("Erro ao conectar com o MongoDB. Verifique se o serviço está ativo e as credenciais estão corretas.")

def get_mongo_conn():
    """Dependency for MongoDB connection"""
    try:
        db = get_db_connection()
        if db is None:
            raise RuntimeError("Falha ao conectar ao MongoDB: banco de dados não inicializado.")
        return db
    except Exception as e:
        raise RuntimeError(f"Erro ao conectar ao MongoDB: {e}")
