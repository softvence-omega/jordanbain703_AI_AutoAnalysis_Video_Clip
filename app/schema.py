from pydantic import BaseModel
from typing import Optional

class paramRequest(BaseModel):
    url: str 
    langCode: str 
    clipLength: int 
    maxClipNumber: int
    templateId: Optional[str] = None  # ✅ Optional


