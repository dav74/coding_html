import base64
import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.agent.graph import compiled_graph
from app.agent.schemas import GraphState, ImageInfo
from app.core.config import settings

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo par image


class ResponseImage(BaseModel):
    filename: str
    data: str        # base64
    content_type: str


class GenerateResponse(BaseModel):
    html: str
    css: str
    status: str
    images: list[ResponseImage]


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("10/minute")
async def generate_site(
    request: Request,
    prompt: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()] = [],
    descriptions: Annotated[str, Form()] = "{}",
):
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Le prompt ne peut pas être vide.")

    try:
        desc_map: dict[str, str] = json.loads(descriptions)
    except json.JSONDecodeError:
        desc_map = {}

    # Lecture des images en mémoire (jamais écrites sur le disque)
    response_images: list[ResponseImage] = []
    image_infos: list[ImageInfo] = []

    for upload in images:
        content = await upload.read()
        if len(content) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"L'image « {upload.filename} » dépasse la taille maximale de 5 Mo.",
            )
        filename = upload.filename or f"image-{len(image_infos) + 1}.jpg"
        response_images.append(ResponseImage(
            filename=filename,
            data=base64.b64encode(content).decode(),
            content_type=upload.content_type or "image/jpeg",
        ))
        image_infos.append(ImageInfo(
            filename=filename,
            description=desc_map.get(filename, ""),
        ))

    initial_state: GraphState = {
        "student_prompt": prompt,
        "images": image_infos,
        "html": "",
        "css": "",
        "review_feedback": [],
        "retry_count": 0,
        "max_retries": settings.MAX_RETRIES,
        "status": "running",
        "error_message": None,
        "validation_passed": False,
        "review_approved": False,
    }

    try:
        result = await compiled_graph.ainvoke(initial_state)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Une erreur interne est survenue. Réessayez dans quelques instants.",
        )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=500,
            detail=result.get(
                "error_message",
                "La génération a échoué. Essayez de reformuler votre prompt.",
            ),
        )

    return GenerateResponse(
        html=result["html"],
        css=result["css"],
        status=result["status"],
        images=response_images,
    )
