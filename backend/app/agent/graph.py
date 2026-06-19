import json
import re
from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.agent.prompts import GENERATOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT
from app.agent.schemas import GraphState, SiteOutput, ReviewOutput
from app.core.config import settings

llm = ChatOpenAI(
    model=settings.MODEL_NAME,
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
    temperature=0.7,
)

generator_llm = llm.with_structured_output(SiteOutput, include_raw=True)
reviewer_llm = llm.with_structured_output(ReviewOutput, include_raw=True)


def _extract_site_from_text(text: str) -> SiteOutput | None:
    # 1. JSON direct
    try:
        data = json.loads(text)
        if "html" in data and "css" in data:
            return SiteOutput(html=data["html"], css=data["css"])
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Objet JSON enfoui dans du texte
    m = re.search(r'\{[^{}]*"html"[^{}]*"css"[^{}]*\}', text, re.DOTALL)
    if not m:
        m = re.search(r'\{[^{}]*"css"[^{}]*"html"[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            if "html" in data and "css" in data:
                return SiteOutput(html=data["html"], css=data["css"])
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Blocs Markdown ```html / ```css
    html_m = re.search(r"```html\s*(.*?)\s*```", text, re.DOTALL)
    css_m = re.search(r"```css\s*(.*?)\s*```", text, re.DOTALL)
    if html_m and css_m:
        return SiteOutput(html=html_m.group(1), css=css_m.group(1))

    return None


def _extract_review_from_text(text: str) -> ReviewOutput | None:
    try:
        data = json.loads(text)
        if "status" in data and "feedback" in data:
            return ReviewOutput(status=data["status"], feedback=data["feedback"])
    except (json.JSONDecodeError, TypeError):
        pass
    return None


async def _invoke_generator(messages: list) -> SiteOutput:
    result = await generator_llm.ainvoke(messages)
    if result["parsed"] is not None:
        return result["parsed"]
    raw_text = result["raw"].content if hasattr(result["raw"], "content") else str(result["raw"])
    extracted = _extract_site_from_text(raw_text)
    if extracted:
        return extracted
    raise ValueError(f"Impossible d'extraire HTML/CSS de la réponse du modèle.")


async def _invoke_reviewer(messages: list) -> ReviewOutput:
    result = await reviewer_llm.ainvoke(messages)
    if result["parsed"] is not None:
        return result["parsed"]
    raw_text = result["raw"].content if hasattr(result["raw"], "content") else str(result["raw"])
    extracted = _extract_review_from_text(raw_text)
    if extracted:
        return extracted
    return ReviewOutput(status="approved", feedback=["Relecture automatique indisponible."])


def _image_context(images: list) -> str:
    if not images:
        return ""
    lines = [
        "\n\n---",
        "Images fournies par l'élève — tu DOIS toutes les utiliser dans le site :",
    ]
    for img in images:
        desc = (img.get("description") or "").strip()
        if desc:
            lines.append(f'• {img["filename"]} — {desc}')
        else:
            lines.append(f'• {img["filename"]} — (sans description : à placer selon le contexte)')
    lines += [
        "",
        'Règles :',
        '- Référence chaque image avec src="images/<nom_du_fichier>" (ex: <img src="images/photo.jpg" alt="...">).',
        "- N'utilise PAS d'images externes (Unsplash, picsum, etc.).",
        "- Utilise TOUTES les images listées ci-dessus au moins une fois.",
    ]
    return "\n".join(lines)


async def generate(state: GraphState) -> GraphState:
    images = state.get("images", [])
    img_ctx = _image_context(images)
    is_retry = bool(state.get("html"))

    if is_retry:
        feedback_lines = "\n".join(f"- {f}" for f in state.get("review_feedback", []))
        user_msg = (
            f"Voici le HTML et CSS précédents :\n\nHTML:\n{state['html']}\n\nCSS:\n{state['css']}\n\n"
            f"Retours du critique :\n{feedback_lines}\n\n"
            f"Corrige précisément ces points et produis un site amélioré."
            + img_ctx
        )
    else:
        user_msg = state["student_prompt"] + img_ctx

    try:
        result = await _invoke_generator([
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        return {**state, "html": result.html, "css": result.css}
    except Exception as e:
        return {
            **state,
            "status": "failed",
            "error_message": f"Erreur lors de la génération : {e}",
            "validation_passed": False,
        }


def validate(state: GraphState) -> GraphState:
    if state.get("status") == "failed":
        return {**state, "validation_passed": False}

    html = state.get("html", "")
    css = state.get("css", "")
    errors: list[str] = []

    if not html.strip():
        errors.append("Le HTML est vide.")
    if not css.strip():
        errors.append("Le CSS est vide.")
    if html and "<!DOCTYPE html>" not in html:
        errors.append("Le HTML ne contient pas <!DOCTYPE html>.")
    if html and '<link rel="stylesheet" href="style.css">' not in html:
        errors.append('Le HTML ne contient pas <link rel="stylesheet" href="style.css">.')
    if css and re.search(r"<[a-zA-Z/]", css):
        errors.append("Le CSS contient des balises HTML.")

    if errors:
        return {
            **state,
            "review_feedback": errors,
            "retry_count": state.get("retry_count", 0) + 1,
            "validation_passed": False,
        }

    return {**state, "validation_passed": True}


def _validate_router(state: GraphState) -> Literal["generate", "fail", "design_review"]:
    if state.get("status") == "failed":
        return "fail"
    if not state.get("validation_passed", False):
        if state.get("retry_count", 0) < state.get("max_retries", 2):
            return "generate"
        return "fail"
    return "design_review"


async def design_review(state: GraphState) -> GraphState:
    try:
        result = await _invoke_reviewer([
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"HTML :\n{state['html']}\n\nCSS :\n{state['css']}",
            },
        ])
        return {
            **state,
            "review_feedback": result.feedback,
            "review_approved": result.status == "approved",
        }
    except Exception:
        return {**state, "review_approved": True, "review_feedback": []}


def _review_router(state: GraphState) -> Literal["refine", "finalize"]:
    if not state.get("review_approved", True):
        if state.get("retry_count", 0) < state.get("max_retries", 2):
            return "refine"
    return "finalize"


async def refine(state: GraphState) -> GraphState:
    feedback_lines = "\n".join(f"- {f}" for f in state.get("review_feedback", []))
    user_msg = (
        f"Voici le HTML et CSS actuels :\n\nHTML:\n{state['html']}\n\nCSS:\n{state['css']}\n\n"
        f"Le directeur artistique demande ces corrections :\n{feedback_lines}\n\n"
        f"Corrige précisément ces points et produis la version améliorée."
    )

    try:
        result = await _invoke_generator([
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        return {
            **state,
            "html": result.html,
            "css": result.css,
            "retry_count": state.get("retry_count", 0) + 1,
        }
    except Exception:
        return {**state, "retry_count": state.get("retry_count", 0) + 1}


def finalize(state: GraphState) -> GraphState:
    return {**state, "status": "done"}


def fail(state: GraphState) -> GraphState:
    msg = state.get("error_message") or (
        "La génération a échoué après plusieurs tentatives. "
        "Essayez de reformuler votre prompt et réessayez."
    )
    return {**state, "status": "failed", "error_message": msg}


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_node("design_review", design_review)
    graph.add_node("refine", refine)
    graph.add_node("finalize", finalize)
    graph.add_node("fail", fail)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate",
        _validate_router,
        {
            "generate": "generate",
            "fail": "fail",
            "design_review": "design_review",
        },
    )
    graph.add_conditional_edges(
        "design_review",
        _review_router,
        {
            "refine": "refine",
            "finalize": "finalize",
        },
    )
    graph.add_edge("refine", "validate")
    graph.add_edge("finalize", END)
    graph.add_edge("fail", END)

    return graph.compile()


compiled_graph = build_graph()
