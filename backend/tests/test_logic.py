from app.ai_service import normalize_prediction
from app.schemas import DefectType


def test_supported_prediction_and_confidence():
    defect, confidence, warning = normalize_prediction('{"predicted_defect_type":"Dent","confidence":0.83}')
    assert defect == DefectType.DENT
    assert confidence == 0.83
    assert warning is None


def test_no_defect_alias():
    defect, confidence, _ = normalize_prediction('{"predicted_defect_type":"no defect","confidence":0.9}')
    assert defect == DefectType.NO_DEFECT
    assert confidence == 0.9


def test_unsupported_category_fails_closed():
    defect, confidence, warning = normalize_prediction('{"predicted_defect_type":"Crack","confidence":0.8}')
    assert defect == DefectType.NO_DEFECT
    assert confidence is None
    assert "unsupported" in warning


def test_malformed_output_is_rejected_instead_of_being_treated_as_a_clean_product():
    import pytest

    with pytest.raises(ValueError, match="malformed JSON"):
        normalize_prediction("not json")


def test_product_match_false_does_not_reject_household_object_test_images():
    defect, confidence, warning = normalize_prediction(
        '{"product_match":false,"predicted_defect_type":"Scratch","confidence":0.76}'
    )
    assert defect == DefectType.SCRATCH
    assert confidence == 0.76
    assert warning is None


def test_missing_product_match_is_accepted_for_generic_product_images():
    defect, confidence, warning = normalize_prediction(
        '{"predicted_defect_type":"Paint Issue","confidence":0.81}'
    )
    assert defect == DefectType.PAINT_ISSUE
    assert confidence == 0.81
    assert warning is None


def test_invalid_confidence_is_discarded():
    defect, confidence, _ = normalize_prediction('{"product_match":true,"predicted_defect_type":"Scratch","confidence":8}')
    assert defect == DefectType.SCRATCH
    assert confidence is None


def test_dashboard_metrics_use_total_as_denominator():
    from types import SimpleNamespace
    from app.metrics import calculate_metrics

    rows = [
        SimpleNamespace(final_defect_type="No Defect", was_overridden=False),
        SimpleNamespace(final_defect_type="Dent", was_overridden=False),
        SimpleNamespace(final_defect_type="Scratch", was_overridden=True),
        SimpleNamespace(final_defect_type="Dent", was_overridden=False),
        SimpleNamespace(final_defect_type="Paint Issue", was_overridden=True),
    ]
    result = calculate_metrics(rows)
    assert result["total_inspected"] == 5
    assert result["passed"] == 1
    assert result["rejected"] == 4
    assert result["defect_rate"] == 80.0
    assert result["ai_acceptance_rate"] == 60.0
    assert result["defect_breakdown"] == {"Scratch": 1, "Dent": 2, "Paint Issue": 1, "Missing Component": 0}


def test_empty_dashboard_metrics_are_zero():
    from app.metrics import calculate_metrics
    result = calculate_metrics([])
    assert result["total_inspected"] == 0
    assert result["defect_rate"] == 0
    assert result["ai_acceptance_rate"] == 0


def test_production_supervisor_is_rejected_by_write_dependency():
    import pytest
    from fastapi import HTTPException
    from app.main import require_engineer

    with pytest.raises(HTTPException) as error:
        require_engineer({"role": "Production Supervisor", "name": "Alex Morgan"})
    assert error.value.status_code == 403


def test_engineer_write_dependency_allows_quality_engineer():
    from app.main import require_engineer

    user = {"role": "Quality Engineer", "name": "Priya Singh"}
    assert require_engineer(user) == user
