from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

# class ChatRequestWithSession(BaseModel):
#     message: str
#     session_id: str = "default"
