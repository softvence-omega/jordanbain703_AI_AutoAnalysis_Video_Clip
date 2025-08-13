from pydantic import BaseModel, Field, conint
from fastapi import UploadFile

class paramRequest(BaseModel):
    url: str 
    lang_code: str 
    clipLength: int 
    maxClipNumber: int
    aspectRatio: int


