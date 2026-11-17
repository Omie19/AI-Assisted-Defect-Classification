import base64
import json
import re
from pathlib import Path
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
            raise ValueError("Vision model returned malformed JSON; retry the classification.") from None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise ValueError("Vision model returned malformed JSON; retry the classification.") from None

    if not isinstance(payload, dict):
        raise ValueError("Vision model returned an invalid response; retry the classification.")

    # Product-family matching is deliberately not required: the exercise accepts
    # ordinary manufactured goods and household objects as test images.

    value = payload.get("predicted_defect_type")
    confidence = payload.get("confidence")
    if isinstance(value, str):
        normalized = value.strip().lower().replace("_", " ").replace("-", " ")
        aliases = {x.lower(): x for x in ALLOWED}
        aliases.update({"none": "No Defect", "no defect": "No Defect", "no defects": "No Defect"})
        value = aliases.get(normalized)
    # Preserve the exercise's fixed defect taxonomy even though the model is free-form.
    # Unsupported categories fail closed to No Defect with a warning for human review.
    if value not in ALLOWED:
        return DefectType.NO_DEFECT, None, "Model returned an unsupported category; defaulted to No Defect. Please inspect manually."
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        confidence = None
    return DefectType(value), float(confidence) if confidence is not None else None, None


def classify_image(path: Path) -> tuple[DefectType, float | None, str | None]:
    # Import the provider SDK only when a live classification is requested;
    # taxonomy/product-scope unit tests do not need network-provider dependencies.
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured. Add it to backend/.env.")
    client = OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=1)
    mime = {".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower(), "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    response = client.responses.create(
        model=settings.openai_model,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": (
                "You are an assistant for a general manufacturing quality-inspection workflow. "
                "Accept and inspect any visible physical product or object in the image. "
                "Test images may include household objects such as phone screens, mugs, bottles, boxes, tools, "
                "plastic containers, toys, furniture parts or other everyday items. Never reject "
                "an image merely because it is not a specific factory product or steel component. "
                "Choose exactly one defect category from this fixed taxonomy: Scratch, Dent, "
                "Paint Issue, Missing Component, or No Defect. Use Scratch for visible surface "
                "abrasion or a linear mark; Dent for a visible indentation or deformation; "
                "Paint Issue for chipped, flaking, uneven, stained or discoloured surface finish "
                "(or a comparable visible finish issue on non-painted materials); Missing Component "
                "only when a required part is clearly expected from the visible context and is absent; "
                "otherwise do not guess about hidden or unseen parts. No Defect means no clear "
                "visible issue can be identified. If the image is ambiguous, choose the closest "
                "visible category and use a conservative confidence score. Do not invent details. "
                'Return only JSON: {"predicted_defect_type": "Dent", "confidence": 0.83}. '
                "The product name or exact model is not required and must not be inferred from the photo."
            )},
            {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"}
        ]}]
    )
    return normalize_prediction(response.output_text)
