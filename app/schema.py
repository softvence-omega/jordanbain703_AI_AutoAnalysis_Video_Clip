from pydantic import BaseModel
from typing import Optional

class paramRequest(BaseModel):
    auth_token: str
    url: str 
    videoType: int
    langCode: str = "en" 
    clipLength: int = 1
    maxClipNumber: int = 2
    templateId: Optional[str] = None  
    prompt: Optional[str] = None
