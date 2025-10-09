from typing import Optional, Dict, Any
import pathlib
from datetime import datetime
import json
from bson.objectid import ObjectId
from pydantic import BaseModel, Field

class PyObjectId(ObjectId):
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate)
            ])
        ])
        
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o): 
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, pathlib.Path):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

class SearchQuery(BaseModel):
    keyword: Optional[str] = None
    termo: Optional[str] = None
    input: Optional[str] = None
    autor: Optional[str] = None
    author: Optional[str] = None
    titulo: Optional[str] = None
    title: Optional[str] = None
    tema: Optional[str] = None
    theme: Optional[str] = None
    capitania: Optional[str] = None
