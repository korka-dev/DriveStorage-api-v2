from datetime import datetime
from beanie import Document, Link
from pydantic import Field
from typing import Optional
from bson import ObjectId

# =========================
# Custom ObjectId compatible Pydantic v2
# =========================
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):  # ✅ info pour compatibilité Pydantic v2
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}


# =========================
# Directory Document
# =========================
class Directory(Document):
    dir_name: str
    owner_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner: str

    class Settings:
        name = "directories"


# =========================
# File Document
# =========================
class File(Document):
    file_name: str
    content_type: str
    file_content: Optional[bytes] = None
    owner_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner: str
    parent: Optional[Link[Directory]] = None
    gridfs_id: PyObjectId = Field(default_factory=PyObjectId)  # ✅ généré automatiquement si non fourni
    file_size_bytes: int = Field(default=0)

    class Settings:
        name = "files"

    class Config:
        json_encoders = {ObjectId: str}  # ✅ conversion automatique pour JSON
