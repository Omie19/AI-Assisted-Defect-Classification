import base64
import json
import re
from pathlib import Path
from openai import OpenAI
from app.config import settings
from app.schemas import DefectType

ALLOWED = {item.value for item in DefectType}


def normalize_prediction(raw: str) -> tuple[DefectType, float | None, str | None]:
    """Parse untrusted model output and constrain it to the fixed taxonomy."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return DefectType.NO_DEFECT, None, "Model returned malformed output; defaulted to No Defect. Please inspect manually."
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return DefectType.NO_DEFECT, None, "Model returned malformed output; defaulted to No Defect. Please inspect manually."

    value = payload.get("predicted_defect_type") if isinstance(payload, dict) else None
    confidence = payload.get("confidence") if isinstance(payload, dict) else None
    if isinstance(value, str):
        normalized = value.strip().lower().replace("_", " ").replace("-", " ")
        aliases = {x.lower(): x for x in ALLOWED}
        aliases.update({"none": "No Defect", "no defect": "No Defect", "no defects": "No Defect"})
        value = aliases.get(normalized)
    if value not in ALLOWED:
        return DefectType.NO_DEFECT, None, "Model returned an unsupported category; defaulted to No Defect. Please inspect manually."
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        confidence = None
    return DefectType(value), float(confidence) if confidence is not None else None, None


def classify_image(path: Path) -> tuple[DefectType, float | None, str | None]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured. Add it to backend/.env.")
    client = OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=1)
    mime = {".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower(), "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    response = client.responses.create(
        model=settings.openai_model,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": (
                "Inspect this manufactured product image. Choose exactly one category: "
                "Scratch, Dent, Paint Issue, Missing Component, No Defect. "
                'Return only JSON: {"predicted_defect_type": "Dent", "confidence": 0.83}. ' 
                "If uncertain, choose No Defect with low confidence; never invent categories."
            )},
            {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"}
        ]}]
    )
    return normalize_prediction(response.output_text)
