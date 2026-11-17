from pathlib import Path
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.ai_service import classify_image
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import AIClassification, Batch, Inspection
from app.metrics import calculate_metrics
from app.schemas import BatchOut, ClassificationOut, DashboardOut, DefectType, InspectionCreate, InspectionOut, UserOut
from app.product_scope import FACTORY_NAME, SUPPORTED_PRODUCT_NAME, ProductScopeError

Base.metadata.create_all(bind=engine)

# create_all does not add columns to an existing SQLite demo database.
# Keep this small additive migration so previously generated local DBs continue to work.
from sqlalchemy import inspect, text
with engine.begin() as connection:
    inspector_columns = {c["name"] for c in inspect(engine).get_columns("ai_classifications")}
    if "inspector_user_id" not in inspector_columns:
        connection.execute(text("ALTER TABLE ai_classifications ADD COLUMN inspector_user_id VARCHAR(20) NOT NULL DEFAULT 'L040223'"))
    inspection_columns = {c["name"] for c in inspect(engine).get_columns("inspections")}
    if "inspector_user_id" not in inspection_columns:
        connection.execute(text("ALTER TABLE inspections ADD COLUMN inspector_user_id VARCHAR(20) NOT NULL DEFAULT 'L040223'"))
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app = FastAPI(title=f"{FACTORY_NAME} — Quality Inspection AI", version="1.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


# Demo identity directory. The client sends only an immutable employee ID;
# display name, role and permissions are always resolved by the backend.
USERS = {
    "L040223": {
        "user_id": "L040223", "name": "Priya Singh", "role": "Quality Engineer",
        "email": "priya.singh@northstar.example", "department": "Quality Assurance",
        "employee_type": "Full-time",
        "permissions": ["view_dashboard", "view_inspections", "upload_images", "classify_products", "create_inspections"],
        "active": True,
    },
    "L040224": {
        "user_id": "L040224", "name": "Alex Morgan", "role": "Production Supervisor",
        "email": "alex.morgan@northstar.example", "department": "Production Operations",
        "employee_type": "Full-time",
        "permissions": ["view_dashboard", "view_inspections"],
        "active": True,
    },
}

def current_user(x_user_id: str = Header(..., alias="X-User-Id")):
    user = USERS.get(x_user_id)
    if not user or not user["active"]:
        raise HTTPException(status_code=401, detail="Unknown or inactive user_id")
    return user


def require_engineer(user=Depends(current_user)):
    if user["role"] != "Quality Engineer":
        raise HTTPException(status_code=403, detail="Only Quality Engineers can log inspections")
    return user


@app.on_event("startup")
def seed_batches():
    with SessionLocal() as db:
        batches = db.scalars(select(Batch)).all()
        by_code = {batch.batch_code: batch for batch in batches}
        seeded_batches = {
            "BATCH-001": "Line 1",
            "BATCH-002": "Line 2",
            "BATCH-003": "Line 3",
        }
        for batch_code, production_line in seeded_batches.items():
            batch = by_code.get(batch_code)
            if batch is None:
                batch = Batch(batch_code=batch_code, product_name=SUPPORTED_PRODUCT_NAME,
                              production_line=production_line)
                db.add(batch)
            else:
                # Normalize earlier demo data so every batch is available for generic product tests.
                batch.product_name = SUPPORTED_PRODUCT_NAME
                batch.production_line = production_line
        # Any extra pre-existing demo batches remain available in the generic workflow.
        for batch in batches:
            batch.product_name = SUPPORTED_PRODUCT_NAME
        db.commit()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/users/me", response_model=UserOut)
def get_current_user(user=Depends(current_user)):
    """Return the complete UI profile for the supplied X-User-Id."""
    return user


@app.get("/api/batches", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db), _=Depends(current_user)):
    # Only expose the demo batches normalized for general product inspection.
    return db.scalars(
        select(Batch).where(Batch.product_name == SUPPORTED_PRODUCT_NAME).order_by(Batch.batch_code)
    ).all()


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
    except ProductScopeError as exc:
        # Kept for compatibility with alternate classifiers; generic image intake normally accepts all products.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Avoid leaking provider details or secrets to the browser.
        raise HTTPException(502, "Vision classification failed. Please retry or classify manually.") from exc
    classification = AIClassification(image_ref=image_ref, predicted_defect_type=defect.value,
        confidence=confidence, model_name=settings.openai_model, inspector=user["name"],
        inspector_user_id=user["user_id"])
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
    # Batch metadata is retained for traceability; the image workflow is not restricted
    # to a particular product family, so household objects are valid test fixtures too.
    classification = db.get(AIClassification, payload.classification_id)
    if not classification:
        raise HTTPException(404, "AI classification not found")
    if classification.inspector_user_id != user["user_id"]:
        raise HTTPException(403, "This AI classification belongs to another inspector")
    if classification.inspection is not None:
        raise HTTPException(409, "This AI classification has already been submitted")
    record = Inspection(
        batch_id=payload.batch_id, classification_id=classification.id,
        final_defect_type=payload.final_defect_type.value,
        was_overridden=classification.predicted_defect_type != payload.final_defect_type.value,
        comments=payload.comments, inspector=user["name"], inspector_user_id=user["user_id"],
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
