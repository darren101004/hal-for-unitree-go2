from pydantic import BaseModel
from typing import Optional, Any


class Response(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    code: int = 0
    extra_data: Optional[dict] = None
