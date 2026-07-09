from datetime import datetime, timezone
import hashlib
import json
import uuid
import pandas as pd


def _df_hash(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    payload = df.sort_index(axis=1).to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def build_scenario_payload(
    scenario_name: str,
    species: str,
    stage: str,
    user: str,
    ingredients_df: pd.DataFrame,
    selected_ingredients: list,
    limits: dict,
    requirements: dict,
    ratios: list,
    result: dict,
    app_version: str = "1.0.0",
    solver_engine: str = "DietFormulator",
    solver_version: str = "1.0.0",
):
    scenario_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    ingredients_hash = _df_hash(ingredients_df)
    ingredients_snapshot = (
        {"columns": list(ingredients_df.columns), "rows": ingredients_df.to_dict(orient="records")}
        if ingredients_df is not None and not ingredients_df.empty
        else {"columns": [], "rows": []}
    )

    diet = (result or {}).get("diet", {}) or {}
    cost_100kg = _safe((result or {}).get("cost", 0), 0)
    cost_kg = cost_100kg / 100
    cost_ton = cost_kg * 1000
    compliance = (result or {}).get("compliance_data", []) or []

    cumple_count = 0
    for r in compliance:
        if str(r.get("Estado", "")).lower() == "cumple":
            cumple_count += 1
    compliance_pct = (cumple_count / len(compliance) * 100) if compliance else 0

    kpis = {
        "cost_100kg": cost_100kg,
        "cost_kg": cost_kg,
        "cost_ton": cost_ton,
        "active_ingredients": len(diet),
        "compliance_pct": compliance_pct
    }

    payload = {
        "spec_version": "1.0.0",
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "created_at": created_at,
        "species": species,
        "stage": stage,
        "owner": {"user": user, "org": "UYWA"},
        "provenance": {
            "app_version": app_version,
            "solver_engine": solver_engine,
            "solver_version": solver_version,
            "currency": "USD",
            "basis": "100kg",
        },
        "inputs": {
            "ingredients_snapshot": ingredients_snapshot,
            "ingredients_hash": ingredients_hash,
            "selected_ingredients": selected_ingredients or [],
            "limits": limits or {"min": {}, "max": {}},
            "requirements": requirements or {},
            "ratios": ratios or [],
        },
        "outputs": {
            "success": bool((result or {}).get("success", False)),
            "message": (result or {}).get("message", ""),
            "diet": diet,
            "cost": cost_100kg,
            "nutritional_values": (result or {}).get("nutritional_values", {}) or {},
            "compliance_data": compliance,
            "constraint_diagnostics": (result or {}).get("constraint_diagnostics", {}) or {},
            "infeasibility_diagnostics": (result or {}).get("infeasibility_diagnostics", []) or [],
        },
        "analytics": {
            "kpis": kpis,
            "economic_drivers": [],
            "technical_drivers": [],
            "quality_flags": [],
        },
        "report": {
            "client_summary": {},
            "technical_appendix": {},
        },
        "extensions": {},
    }

    return payload


def scenario_to_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
