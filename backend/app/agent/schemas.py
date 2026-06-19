from typing import Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class SiteOutput(BaseModel):
    html: str = Field(description="Document HTML complet, de <!DOCTYPE html> à </html>.")
    css: str = Field(description="Contenu complet de style.css, sans aucune balise HTML.")


class ImageInfo(TypedDict):
    filename: str
    description: str


class GraphState(TypedDict):
    student_prompt: str
    images: list[ImageInfo]
    html: str
    css: str
    review_feedback: list[str]
    retry_count: int
    max_retries: int
    status: Literal["running", "done", "failed"]
    error_message: Optional[str]
    validation_passed: bool
