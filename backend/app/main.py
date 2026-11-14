from pathlib import Path
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.ai_service import classify_image
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import AIClassification, Batch, Inspection
from app.metrics import calculate_metrics
from app.schemas import BatchOut, ClassificationOut, DashboardOut, DefectType, InspectionCreate, InspectionOut

Base.metadata.create_all(bind=engine)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Quality Inspection AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


def current_user(x_user_role: str = Header(default="Quality Engineer"), x_user_name: str = Header(default="Demo Engineer")):
    allowed = {"Quality Engineer", "Production Supervisor"}
    if x_user_role not in allowed:
        raise HTTPException(status_code=401, detail="Unknown demo role")
    return {"role": x_user_role, "name": x_user_name[:120]}


def require_engineer(user=Depends(current_user)):
    if user["role"] != "Quality Engineer":
        raise HTTPException(status_code=403, detail="Only Quality Engineers can log inspections")
    return user


@app.on_event("startup")
def seed_batches():
    with SessionLocal() as db:
        if db.scalar(select(func.count(Batch.id))) == 0:
            db.add_all([
                Batch(batch_code="BATCH-001", product_name="Steel Bracket — Model X200", production_line="Line 3"),
                Batch(batch_code="BATCH-002", product_name="Aluminium Housing — Model A10", production_line="Line 1"),
            ])
            db.commit()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/batches", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.scalars(select(Batch).order_by(Batch.batch_code)).all()


@app.post("/api/uploads")
def upload_image(file: UploadFile = File(...), _=Depends(require_engineer)):
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed:
        raise HTTPException(415, "Upload a JPEG, PNG, or WebP image")
    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Image exceeds the 8 MB limit")
    if not content:
        raise HTTPException(400, "Image is empty")
    # Verify that the bytes are actually a decodable image, not just a spoofed MIME type.
    from PIL import Image, UnidentifiedImageError
    import io, uuid
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "File is not a valid image") from None
    name = f"{uuid.uuid4().hex}{allowed[file.content_type]}"
    target = Path(settings.upload_dir) / name
    target.write_bytes(content)
    return {"image_ref": f"/uploads/{name}"}


@app.post("/api/classify", response_model=ClassificationOut)
def classify(image_ref: str, db: Session = Depends(get_db), user=Depends(require_engineer)):
    if not image_ref.startswith("/uploads/") or "/.." in image_ref:
        raise HTTPException(400, "Invalid image reference")
    path = Path(settings.upload_dir) / Path(image_ref).name
    if not path.is_file():
        raise HTTPException(404, "Uploaded image not found")
    try:
        defect, confidence, warning = classify_image(path)
    except Exception as exc:
        # Avoid leaking provider details or secrets to the browser.
        raise HTTPException(502, "Vision classification failed. Please retry or classify manually.") from exc
    classification = AIClassification(image_ref=image_ref, predicted_defect_type=defect.value,
        confidence=confidence, model_name=settings.openai_model, inspector=user["name"])
    db.add(classification)
    db.commit()
    db.refresh(classification)
    return ClassificationOut(classification_id=classification.id, predicted_defect_type=defect,
        confidence=confidence, model=settings.openai_model, warning=warning)


@app.post("/api/inspections", response_model=InspectionOut, status_code=201)
def create_inspection(payload: InspectionCreate, db: Session = Depends(get_db), user=Depends(require_engineer)):
    batch = db.get(Batch, payload.batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    classification = db.get(AIClassification, payload.classification_id)
    if not classification:
        raise HTTPException(404, "AI classification not found")
    if classification.inspector != user["name"]:
        raise HTTPException(403, "This AI classification belongs to another inspector")
    if classification.inspection is not None:
        raise HTTPException(409, "This AI classification has already been submitted")
    record = Inspection(
        batch_id=payload.batch_id, classification_id=classification.id,
        final_defect_type=payload.final_defect_type.value,
        was_overridden=classification.predicted_defect_type != payload.final_defect_type.value,
        comments=payload.comments, inspector=user["name"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return db.scalar(select(Inspection).options(joinedload(Inspection.batch), joinedload(Inspection.classification)).where(Inspection.id == record.id))


@app.get("/api/inspections", response_model=list[InspectionOut])
def list_inspections(defect_type: DefectType | None = Query(default=None), batch_id: int | None = None, db: Session = Depends(get_db), _=Depends(current_user)):
    stmt = select(Inspection).options(joinedload(Inspection.batch), joinedload(Inspection.classification)).order_by(Inspection.inspected_at.desc())
    if defect_type:
        stmt = stmt.where(Inspection.final_defect_type == defect_type.value)
    if batch_id:
        stmt = stmt.where(Inspection.batch_id == batch_id)
    return db.scalars(stmt).unique().all()


@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(batch_id: int | None = None, db: Session = Depends(get_db), _=Depends(current_user)):
    stmt = select(Inspection)
    if batch_id:
        stmt = stmt.where(Inspection.batch_id == batch_id)
    rows = db.scalars(stmt).unique().all()
    return DashboardOut(**calculate_metrics(rows))
