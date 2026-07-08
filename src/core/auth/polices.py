from typing import Dict, Set


# Features funcionales que podemos encender/apagar por plan
# (sin romper cálculos, solo controlando acceso UI/módulos)
PLAN_FEATURES: Dict[str, Set[str]] = {
    "Demo": {
        "formulator_aves",
        "results_basic",
        "charts_basic",
    },
    "Profesional": {
        "formulator_aves",
        "formulator_cerdos",
        "results_basic",
        "results_advanced",
        "charts_basic",
        "charts_advanced",
        "scenario_compare",
        "export_project_zip",
        "import_project_zip",
    },
    "Premium": {
        "formulator_aves",
        "formulator_cerdos",
        "formulator_rumiantes",
        "results_basic",
        "results_advanced",
        "charts_basic",
        "charts_advanced",
        "scenario_compare",
        "export_project_zip",
        "import_project_zip",
        "tool_energy_predictor",
        "tool_raw_material_analyzer",
    },
    "Admin": {
        "formulator_aves",
        "formulator_cerdos",
        "formulator_rumiantes",
        "results_basic",
        "results_advanced",
        "charts_basic",
        "charts_advanced",
        "scenario_compare",
        "export_project_zip",
        "import_project_zip",
        "tool_energy_predictor",
        "tool_raw_material_analyzer",
        "admin_users",
        "admin_plans",
    },
}


# Fallback cuando el plan no está mapeado
DEFAULT_FEATURES = {
    "formulator_aves",
    "results_basic",
    "charts_basic",
}


def normalize_plan_name(plan: str | None) -> str:
    if not plan:
        return "Demo"

    p = str(plan).strip().lower()

    aliases = {
        "demo": "Demo",
        "profesional": "Profesional",
        "pro": "Profesional",
        "premium": "Premium",
        "admin": "Admin",
    }

    return aliases.get(p, "Demo")


def get_user_plan(user: dict | None) -> str:
    if not user:
        return "Demo"

    # prioridad al campo plan explícito
    plan = normalize_plan_name(user.get("plan"))
    if plan:
        return plan

    # compatibilidad con legado premium bool
    if bool(user.get("premium", False)):
        return "Profesional"

    return "Demo"


def get_plan_features(plan: str | None) -> Set[str]:
    normalized = normalize_plan_name(plan)
    return PLAN_FEATURES.get(normalized, DEFAULT_FEATURES)


def get_user_features(user: dict | None) -> Set[str]:
    plan = get_user_plan(user)
    return get_plan_features(plan)


def has_feature(user: dict | None, feature: str) -> bool:
    return feature in get_user_features(user)


def available_formulators(user: dict | None) -> list[str]:
    feats = get_user_features(user)
    options = []

    if "formulator_aves" in feats:
        options.append("Aves")
    if "formulator_cerdos" in feats:
        options.append("Cerdos")
    if "formulator_rumiantes" in feats:
        options.append("Rumiantes")

    return options


def available_tools(user: dict | None) -> list[str]:
    feats = get_user_features(user)
    tools = []

    if "tool_energy_predictor" in feats:
        tools.append("Predictor de Energía")
    if "tool_raw_material_analyzer" in feats:
        tools.append("Analizador de Materias Primas")
    if "scenario_compare" in feats:
        tools.append("Comparador de Escenarios")

    return tools
