import uuid
from pydantic import BaseModel


class SurveySessionResponse(BaseModel):
    session_token: str
    opening_message: str


class SurveyMessageRequest(BaseModel):
    session_token: str
    content: str
