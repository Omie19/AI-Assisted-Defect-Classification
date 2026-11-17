from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class DefectType(str, Enum):
    SCRATCH = "Scratch"
    DENT = "Dent"
    PAINT_ISSUE = "Paint Issue"
    MISSING_COMPONENT = "Missing Component"
    NO_DEFECT = "No Defect"


class BatchOut(BaseModel):
    id: int
    batch_code: str
    product_name: str
    production_line: str
    model_config = ConfigDict(from_attributes=True)


class ClassificationOut(BaseModel):
    classification_id: int
    predicted_defect_type: DefectType
    confidence: float | None = Field(default=None, ge=0, le=1)
    model: str
    warning: str | None = None


class InspectionCreate(BaseModel):
    batch_id: int
    classification_id: int
    final_defect_type: DefectType
    comments: str | None = Field(default=None, max_length=3000)


class InspectionOut(BaseModel):
    id: int
    batch_id: int
    image_ref: str
    ai_predicted_defect_type: DefectType
    ai_confidence: float | None
    final_defect_type: DefectType
    was_overridden: bool
    comments: str | None
    inspector: str
    inspected_at: datetime
    batch: BatchOut
    model_config = ConfigDict(from_attributes=True)


class DashboardOut(BaseModel):
    total_inspected: int
    passed: int
    rejected: int
    defect_rate: float
    ai_acceptance_rate: float
    defect_breakdown: dict[str, int]


class UserOut(BaseModel):
    user_id: str
    name: str
    role: str
    email: str
    department: str
    employee_type: str
    permissions: list[str]
    active: bool


class UserOut(BaseModel):
    user_id: str
    name: str
    role: str
    email: str
    department: str
    employee_type: str
    permissions: list[str]
    active: bool
