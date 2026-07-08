import os
import io
import json
import zipfile
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from src.core.io.data_access import load_ingredients, get_nutrient_list
from src.core.formulation.presets import get_stage_preset
from src.adapters.optimization_adapter import OptimizationAdapter

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.ui.components.tables import render_table


def _safe_float(v, default=0.0):
    try:
        if isinstance(v, str):
            v = v.replace(",", ".")
        return float(v)
    except Exception:
        return default


def _normalize_bound(v):
    x = _safe_float(v, 0)
    return x if x > 0 else 0.0


def _resolve_ema_for_stage_from_preset(etapa, preset, nutrients_all):
    ema_in_preset = [c for c in ["EMA_POLLIT", "EMA_AVES"] if c in (preset or {})]
    ema_in_matrix = [c for c in ["EMA_POLLIT", "EMA_AVES"] if c in (nutrients_all or [])]

    if len(ema_in_preset) == 1:
        preferred = ema_in_preset[0]
        reason = "preset"
    elif len(ema_in_preset) > 1:
        preferred = "EMA_AVES" if "EMA_AVES" in ema_in_preset else ema_in_preset[0]
        reason = "preset_ambiguous"
    else:
        preferred = "EMA_AVES" if "EMA_AVES" in ema_in_matrix else (
            "EMA_POLLIT" if "EMA_POLLIT" in ema_in_matrix else None
        )
        reason = "fallback_matrix"

    other = "EMA_POLLIT" if preferred == "EMA_AVES" else ("EMA_AVES" if preferred == "EMA_POLLIT" else None)
    return preferred, other, reason


def _load_ingredients_robust(uploaded_file=None):
    if uploaded_file is not None:
        df = load_ingredients(uploaded_file)
        if df is not None and not df.empty:
            return df.copy()

    cached = st.session_state.get("aves_loaded_ingredients_df")
    if cached is not None and not cached.empty:
        return cached.copy()

    root = os.path.abspath(os.getcwd())
    p_csv = os.path.join(root, "data-files", "matriz_ingredientes.csv")
    p_xlsx = os.path.join(root, "data-files", "matriz_ingredientes.xlsx")

    try:
        if os.path.exists(p_csv):
            df = pd.read_csv(p_csv)
            if not df.empty:
                return df.copy()
    except Exception:
        pass

    try:
        if os.path.exists(p_xlsx):
            df = pd.read_excel(p_xlsx)
            if not df.empty:
                return df.copy()
    except Exception:
        pass

    return load_ingredients(uploaded_file)


def _create_ingredients_csv(df_ingredientes):
    return df_ingredientes.to_csv(index=False)


def _create_project_zip_export(
    ingredientes_df, req_data, etapa, usuario,
    min_limits=None, max_limits=None, ratios=None, nutrientes_seleccionados=None
):
    min_limits = min_limits or {}
    max_limits = max_limits or {}
    ratios = ratios or []
    nutrientes_seleccionados = nutrientes_seleccionados or []

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ingredients.csv", ingredientes_df.to_csv(index=False))
        req_df = pd.DataFrame([
            {"nutriente": n, "min_value": vals.get("min", 0), "max_value": vals.get("max", 0)}
            for n, vals in req_data.items()
        ])
        zf.writestr("requirements.csv", req_df.to_csv(index=False))
        zf.writestr("ingredient_limits.json", json.dumps({"min_limits": min_limits, "max_limits": max_limits}, indent=2, ensure_ascii=False))
        zf.writestr("ratios.json", json.dumps(ratios, indent=2, ensure_ascii=False))
        zf.writestr("project_metadata.json", json.dumps({
            "especie": "Aves",
            "etapa": etapa,
            "usuario": usuario,
            "fecha": date.today().isoformat(),
            "version": "modular-aves-1.2",
            "nutrientes_seleccionados": nutrientes_seleccionados,
        }, indent=2, ensure_ascii=False))

    zip_buffer.seek(0)
    return zip_buffer


def _load_project_zip(uploaded_zip):
    with zipfile.ZipFile(uploaded_zip, "r") as zf:
        names = set(zf.namelist())
        required = {"ingredients.csv", "requirements.csv", "project_metadata.json"}
        missing = required - names
        if missing:
            return None, [f"Faltan archivos obligatorios en ZIP: {', '.join(sorted(missing))}"]

        with zf.open("ingredients.csv") as f:
            ingredients_df = pd.read_csv(f)
        with zf.open("requirements.csv") as f:
            requirements_df = pd.read_csv(f)
        with zf.open("project_metadata.json") as f:
            metadata = json.load(f)

        limits = {"min_limits": {}, "max_limits": {}}
        ratios = []
        if "ingredient_limits.json" in names:
            with zf.open("ingredient_limits.json") as f:
                limits = json.load(f)
        if "ratios.json" in names:
            with zf.open("ratios.json") as f:
                ratios = json.load(f)

        return {
            "ingredients_df": ingredients_df,
            "requirements_df": requirements_df,
            "metadata": metadata,
            "limits": limits,
            "ratios": ratios,
        }, []


def _render_progress(min_val, max_val, obtained):
    if min_val == 0 and max_val == 0:
        return "—", "—"
    pct = (obtained / min_val) * 100 if min_val > 0 else ((obtained / max_val) * 100 if max_val > 0 else 100)
    emoji = "✅" if abs(pct - 100) < 1 else ("❌" if pct < 100 else "⚠️")
    return f"{emoji} {pct:.1f}%", pct


def _shadow_impact_pct(shadow_price, total_cost_100kg):
    if shadow_price is None:
        return "—", None
    cost_per_kg = (total_cost_100kg or 0) / 100
    if cost_per_kg <= 0:
        return "—", None
    pct = abs(float(shadow_price)) / cost_per_kg * 100
    return f"{pct:.3f}%", pct


def _marginal_cost_ton(shadow_price):
    if shadow_price is None:
        return "—"
    return f"${abs(float(shadow_price))*1000:.2f}/ton"


def _impact_class(pct):
    if pct is None:
        return "Bajo"
    if pct > 2:
        return "Alto"
    if pct >= 0.5:
        return "Medio"
    return "Bajo"


def _get_limiting_ing(nutriente, diet_map, df_sel):
    try:
        if df_sel is None or df_sel.empty or nutriente not in df_sel.columns:
            return "—"
        aportes, total = {}, 0.0
        for ing, pct in (diet_map or {}).items():
            row = df_sel[df_sel["Ingrediente"] == ing]
            if row.empty:
                continue
            val = float(pd.to_numeric(row.iloc[0].get(nutriente, 0), errors="coerce") or 0)
            ap = val * (float(pct) / 100.0)
            aportes[ing] = ap
            total += ap
        if total <= 0 or not aportes:
            return "—"
        ing_top, ap_top = max(aportes.items(), key=lambda x: x[1])
        return f"{ing_top} ({(ap_top/total)*100:.0f}%)"
    except Exception:
        return "—"


def _validate_before_solve(df_sel, nutrients, req_input, min_limits, max_limits, ratios):
    errors, warnings = [], []

    if df_sel is None or df_sel.empty:
        return ["No hay ingredientes seleccionados para formular."], warnings

    if "Ingrediente" not in df_sel.columns:
        errors.append("La matriz no contiene columna 'Ingrediente'.")
    if "precio" not in df_sel.columns:
        errors.append("La matriz no contiene columna 'precio'.")
    if not nutrients:
        errors.append("No hay nutrientes seleccionados.")

    smin = sum(_safe_float(min_limits.get(i, 0), 0) for i in df_sel["Ingrediente"].tolist())
    if smin > 100:
        errors.append(f"La suma de mínimos por ingrediente es {smin:.2f}% (>100%).")

    active = 0
    for n in nutrients:
        mn = _safe_float(req_input.get(n, {}).get("min", 0), 0)
        mx = _safe_float(req_input.get(n, {}).get("max", 0), 0)
        if mn < 0 or mx < 0:
            errors.append(f"Nutriente '{n}' tiene valores negativos.")
        if mx > 0 and mn > mx:
            errors.append(f"Nutriente '{n}' tiene mínimo mayor que máximo.")
        if mn > 0 or mx > 0:
            active += 1
    if active == 0:
        errors.append("No hay restricciones nutricionales activas (min/max > 0).")

    for r in ratios:
        num, den, op, val = r.get("numerador"), r.get("denominador"), r.get("operador"), _safe_float(r.get("valor", 0), 0)
        if not num or not den or num == den:
            errors.append("Hay ratio inválido (numerador/denominador).")
        if op not in {">=", "<=", "="}:
            errors.append("Hay ratio con operador inválido.")
        if val <= 0:
            errors.append("Hay ratio con valor <= 0.")
        if den and _safe_float(req_input.get(den, {}).get("min", 0), 0) <= 0:
            warnings.append(f"Ratio {num}/{den}: denominador sin mínimo explícito ({den}).")

    return errors, warnings


def render():
    st.title("Formulador · Aves")
    st.caption("Flujo premium modular: matriz, límites, requerimientos en vivo, ratios y formulación completa.")

    with st.expander("Cargar proyecto completo UYWA (.zip)", expanded=False):
        up_zip = st.file_uploader("Subir ZIP de proyecto", type=["zip"], key="aves_project_zip_upload")
        if up_zip is not None and st.button("Restaurar proyecto", key="aves_restore_zip_btn"):
            data, errors = _load_project_zip(up_zip)
            if errors:
                render_card("Error al restaurar proyecto", " | ".join(errors), variant="danger")
            else:
                st.session_state["aves_loaded_ingredients_df"] = data["ingredients_df"].copy()

                # NUEVO: persistir etapa restaurada
                restored_etapa = str(data.get("metadata", {}).get("etapa", "")).strip()
                if restored_etapa:
                    st.session_state["aves_etapa"] = restored_etapa

                req_data, nutr_loaded = {}, []
                rdf = data["requirements_df"]
                if not rdf.empty and "nutriente" in rdf.columns:
                    for _, row in rdf.iterrows():
                        n = str(row.get("nutriente", "")).strip()
                        if not n:
                            continue
                        mn = _normalize_bound(row.get("min_value", 0))
                        mx = _normalize_bound(row.get("max_value", 0))
                        req_data[n] = {"min": mn, "max": mx}
                        st.session_state[f"aves_req_min_{n}"] = mn
                        st.session_state[f"aves_req_max_{n}"] = mx
                        nutr_loaded.append(n)

                st.session_state["aves_req_input"] = req_data
                st.session_state["aves_nutrients_selected"] = nutr_loaded
                st.session_state["aves_min_limits_loaded"] = data["limits"].get("min_limits", {})
                st.session_state["aves_max_limits_loaded"] = data["limits"].get("max_limits", {})
                st.session_state["aves_ingredientes_limitar"] = sorted(set(
                    list(st.session_state["aves_min_limits_loaded"].keys()) +
                    list(st.session_state["aves_max_limits_loaded"].keys())
                ))
                st.session_state["aves_ratios"] = data.get("ratios", [])

                idf = data["ingredients_df"]
                if "Ingrediente" in idf.columns:
                    st.session_state["aves_ingredientes_sel"] = idf["Ingrediente"].dropna().astype(str).tolist()

                render_card(
                    "Proyecto restaurado",
                    f"Aves - {data['metadata'].get('etapa','N/A')} ({data['metadata'].get('fecha','N/A')})",
                    variant="success",
                )
                st.rerun()

    render_section("Matriz de ingredientes", "Carga manual o usa data-files/matriz_ingredientes.*")
    up = st.file_uploader("Matriz de ingredientes (.csv/.xlsx)", type=["csv", "xlsx"], key="aves_matriz_upload")
    df = _load_ingredients_robust(up)

    if df is None or df.empty:
        render_card("Sin matriz activa", "No se encontró matriz.", variant="warning")
        return
    if "Ingrediente" not in df.columns or "precio" not in df.columns:
        render_card("Formato inválido", "La matriz debe incluir 'Ingrediente' y 'precio'.", variant="danger")
        return

    df = df.copy()
    df["Ingrediente"] = df["Ingrediente"].astype(str)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)

    render_card("Matriz activa", f"Ingredientes disponibles: {len(df)}", variant="success")

    render_section("Selección de ingredientes")
    ing_all = df["Ingrediente"].dropna().tolist()
    pre = st.session_state.get("aves_ingredientes_sel", ing_all[: min(25, len(ing_all))])

    ingredientes_sel = st.multiselect("Ingredientes a usar", ing_all, default=[i for i in pre if i in ing_all], key="aves_ingredientes_sel")
    if not ingredientes_sel:
        render_card("Selección vacía", "Selecciona al menos un ingrediente.", variant="warning")
        return

    df_sel = df[df["Ingrediente"].isin(ingredientes_sel)].copy()
    with st.expander("Ver o editar composición de ingredientes seleccionados", expanded=False):
        df_sel = st.data_editor(df_sel, use_container_width=True, num_rows="dynamic", key="aves_df_editor")

    render_section("Requerimientos nutricionales")
    etapas_aves = [
        "Broiler Iniciación", "Broiler Crecimiento", "Broiler Cebo", "Broiler Acabado",
        "Pollita Recría 0-5", "Pollita Recría 5-10", "Pollita Recría 10-17",
        "Pollita Inicio Puesta", "Ponedora Pre-Pico", "Ponedora Inicio Postura",
        "Ponedora Final Postura", "Ponedora Problemas Cascara",
    ]

    # NUEVO: etapa robusta con fallback si lo restaurado no existe
    etapa_default = st.session_state.get("aves_etapa", etapas_aves[0])
    if etapa_default not in etapas_aves:
        etapa_default = etapas_aves[0]
    etapa_idx = etapas_aves.index(etapa_default)

    etapa = st.selectbox("Etapa (Aves)", etapas_aves, index=etapa_idx, key="aves_etapa")
    nutrients_all = get_nutrient_list(df_sel if not df_sel.empty else df)
    preset = get_stage_preset("Aves", etapa)
    preset_compat = [n for n in preset.keys() if n in nutrients_all]

    preferred_ema, other_ema, ema_reason = _resolve_ema_for_stage_from_preset(etapa, preset, nutrients_all)

    if preferred_ema and other_ema and preferred_ema in preset_compat and other_ema in preset_compat:
        preset_compat = [n for n in preset_compat if n != other_ema]
        st.warning(f"Preset ambiguo en EMA para '{etapa}'. Se priorizó {preferred_ema}.")

    if st.button("Cargar preset completo", key="aves_load_preset"):
        selected = preset_compat.copy()
        if preferred_ema and other_ema:
            selected = [n for n in selected if n != other_ema]
            if preferred_ema in nutrients_all and preferred_ema not in selected:
                selected.insert(0, preferred_ema)
        st.session_state["aves_nutrients_selected"] = selected
        for n in selected:
            st.session_state[f"aves_req_min_{n}"] = float(preset.get(n, {}).get("min", 0) or 0)
            st.session_state[f"aves_req_max_{n}"] = float(preset.get(n, {}).get("max", 0) or 0)
        st.rerun()

    default_selected = st.session_state.get("aves_nutrients_selected", preset_compat[: min(14, len(preset_compat))])
    if preferred_ema and other_ema:
        default_selected = [n for n in default_selected if n != other_ema]
        if preferred_ema in nutrients_all and preferred_ema not in default_selected:
            default_selected = [preferred_ema] + default_selected

    selected_nutrients = st.multiselect("Nutrientes a considerar", nutrients_all, default=default_selected, key="aves_nutrients_selected")
    if preferred_ema and other_ema and preferred_ema in selected_nutrients and other_ema in selected_nutrients:
        selected_nutrients = [n for n in selected_nutrients if n != other_ema]
        st.session_state["aves_nutrients_selected"] = selected_nutrients

    with st.expander("Debug EMA etapa/preset", expanded=False):
        st.write("Etapa:", etapa)
        st.write("EMA en preset:", [c for c in ["EMA_POLLIT", "EMA_AVES"] if c in preset.keys()])
        st.write("EMA activo:", preferred_ema, "| fuente:", ema_reason)

    if not selected_nutrients:
        st.info("Selecciona nutrientes para continuar.")
        return

    # ... (tu bloque de tabla preview, ratios, solver final y vista previa puede quedarse igual al que ya tenías)
    # Para no romperte nada, mantén exactamente tu bloque desde "# 6) Ratios" en adelante.
