from app.schemas import DefectType


def calculate_metrics(rows):
    total = len(rows)
    passed = sum(row.final_defect_type == DefectType.NO_DEFECT.value for row in rows)
    rejected = total - passed
    accepted = sum(not row.was_overridden for row in rows)
    breakdown = {
        defect.value: sum(row.final_defect_type == defect.value for row in rows)
        for defect in DefectType
        if defect != DefectType.NO_DEFECT
    }
    return {
        "total_inspected": total,
        "passed": passed,
        "rejected": rejected,
        "defect_rate": round(rejected / total * 100, 2) if total else 0.0,
        "ai_acceptance_rate": round(accepted / total * 100, 2) if total else 0.0,
        "defect_breakdown": breakdown,
    }
