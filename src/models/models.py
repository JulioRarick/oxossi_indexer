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
    captaincy: Optional[str] = None
    data: Optional[str] = None
    date: Optional[str] = None
    localizacao: Optional[str] = None
    places: Optional[str] = None
    nome: Optional[str] = None
    names: Optional[str] = None

class ContextMatchQuery(BaseModel):
    termo: Optional[str] = None
    autor: Optional[str] = None
    titulo: Optional[str] = None
    tema: Optional[str] = None
    capitania: Optional[str] = None
    data: Optional[str] = None
    localizacao: Optional[str] = None
    nome: Optional[str] = None
    pdf_path: Optional[str] = None

class PDFSummary(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    filename: str
    processed_at: Optional[datetime] = None
    length: Optional[int] = None
    
    model_config = {
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "id": "5f50d22f2ad67c02abe4e999",
                "filename": "example.pdf",
                "processed_at": "2025-06-24T12:00:00",
                "length": 1000
            }
        },
        "populate_by_name": True
    }
    
    def model_dump_json(self, **kwargs):
        """Custom JSON serialization for MongoDB ObjectId and datetime"""
        json_dict = self.model_dump(**kwargs)
        for k, v in json_dict.items():
            if isinstance(v, ObjectId):
                json_dict[k] = str(v)
            elif isinstance(v, datetime):
                json_dict[k] = v.isoformat() if v else None
        return json.dumps(json_dict)

class PDFDetail(PDFSummary):
    file_path: Optional[str] = None
    full_text: Optional[str] = None
    date_analysis: Optional[dict] = None
    names_analysis: Optional[dict] = None
    places_analysis: Optional[dict] = None
    references_analysis: Optional[dict] = None
    themes_analysis: Optional[dict] = None
