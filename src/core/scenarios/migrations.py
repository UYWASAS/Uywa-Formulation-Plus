def migrate_scenario(payload: dict) -> dict:
    spec = payload.get("spec_version", "")

    # v1.0.0 actual: no-op
    if spec == "1.0.0":
        return payload

    # fallback: si no trae versión, asumir legacy y adaptar mínimo
    if not spec:
        payload["spec_version"] = "1.0.0"
        payload.setdefault("analytics", {"kpis": {}, "economic_drivers": [], "technical_drivers": [], "quality_flags": []})
        payload.setdefault("extensions", {})
        return payload

    raise ValueError(f"Versión de escenario no soportada: {spec}")
