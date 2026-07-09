import os
import json
import zipfile
from io import BytesIO

import pandas as pd
import streamlit as st

from src.core.io.data_access import load_ingredients, get_nutrient_list
from src.core.formulation.presets import get_stage_preset
from src.adapters.optimization_adapter import OptimizationAdapter

from src.core.scenarios.build_scenario import build_scenario_payload, scenario_to_json

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card
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
    elif len(ema_in_preset) > 1:
        preferred = "EMA_AVES" if "EMA_AVES" in ema_in_preset else ema_in_preset[0]
    else:
        preferred = "EMA_AVES" if "EMA_AVES" in ema_in_matrix else (
            "EMA_POLLIT" if "EMA_POLLIT" in ema_in_matrix else None
        )

    other = "EMA_POLLIT" if preferred == "EMA_AVES" else ("EMA_AVES" if preferred == "EMA_POLLIT" else None)
    return preferred, other


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
        return f"{ing_top} ({(ap_top / total) * 100:.0f}%)"
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

    smin = sum(_safe_float(min_limits.get(i, 0), 0) for i in min_limits.keys())
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
        num = r.get("numerador")
        den = r.get("denominador")
        op = r.get("operador")
        val = _safe_float(r.get("valor", 0), 0)
        if not num or not den or num == den:
            errors.append("Hay ratio inválido (numerador/denominador).")
        if op not in {">=", "<=", "="}:
            errors.append("Hay ratio con operador inválido.")
        if val <= 0:
            errors.append("Hay ratio con valor <= 0.")
        den_min = _safe_float(req_input.get(den, {}).get("min", 0), 0)
        if den and den_min <= 0:
            warnings.append(f"Ratio {num}/{den}: denominador sin mínimo explícito ({den}).")

    return errors, warnings


def render_formulation_aves():
    st.subheader("Formulación")

    with st.expander("Cargar proyecto completo UYWA (.zip)", expanded=False):
        up_zip = st.file_uploader("Subir ZIP de proyecto", type=["zip"], key="aves_project_zip_upload")
        if up_zip is not None and st.button("Restaurar proyecto", key="aves_restore_zip_btn"):
            data, errors = _load_project_zip(up_zip)
            if errors:
                render_card("Error al restaurar proyecto", " | ".join(errors), variant="danger")
            else:
                st.session_state["aves_loaded_ingredients_df"] = data["ingredients_df"].copy()
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
                st.session_state["aves_ingredientes_limitar"] = sorted(
                    set(list(st.session_state["aves_min_limits_loaded"].keys()) +
                        list(st.session_state["aves_max_limits_loaded"].keys()))
                )
                st.session_state["aves_ratios"] = data.get("ratios", [])
                idf = data["ingredients_df"]
                if "Ingrediente" in idf.columns:
                    st.session_state["aves_ingredientes_sel"] = idf["Ingrediente"].dropna().astype(str).tolist()
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

    ing_all = df["Ingrediente"].dropna().tolist()
    pre = st.session_state.get("aves_ingredientes_sel", ing_all[: min(25, len(ing_all))])
    ingredientes_sel = st.multiselect("Ingredientes a usar", ing_all, default=[i for i in pre if i in ing_all], key="aves_ingredientes_sel")
    if not ingredientes_sel:
        return

    df_sel = df[df["Ingrediente"].isin(ingredientes_sel)].copy()
    with st.expander("Ver o editar composición de ingredientes seleccionados", expanded=False):
        df_sel = st.data_editor(df_sel, use_container_width=True, num_rows="dynamic", key="aves_df_editor")

    ing_limit = st.multiselect("Ingredientes con límites", ingredientes_sel, default=st.session_state.get("aves_ingredientes_limitar", []), key="aves_ingredientes_limitar")
    min_limits, max_limits = {}, {}
    min_loaded = st.session_state.get("aves_min_limits_loaded", {})
    max_loaded = st.session_state.get("aves_max_limits_loaded", {})
    for ing in ing_limit:
        c = st.columns([2, 1, 1])
        c[0].write(ing)
        max_v = c[1].number_input("max", min_value=0.0, max_value=100.0, value=float(st.session_state.get(f"aves_max_{ing}", max_loaded.get(ing, 100.0))), key=f"aves_max_{ing}", label_visibility="collapsed")
        min_v = c[2].text_input("min", value=str(st.session_state.get(f"aves_min_{ing}", min_loaded.get(ing, ""))), key=f"aves_min_{ing}", label_visibility="collapsed")
        min_limits[ing] = _safe_float(min_v, 0)
        max_limits[ing] = _safe_float(max_v, 0)

    etapas_aves = [
        "Broiler Iniciación", "Broiler Crecimiento", "Broiler Cebo", "Broiler Acabado",
        "Pollita Recría 0-5", "Pollita Recría 5-10", "Pollita Recría 10-17",
        "Pollita Inicio Puesta", "Ponedora Pre-Pico", "Ponedora Inicio Postura",
        "Ponedora Final Postura", "Ponedora Problemas Cascara",
    ]
    etapa_default = st.session_state.get("aves_etapa", etapas_aves[0])
    if etapa_default not in etapas_aves:
        etapa_default = etapas_aves[0]
    etapa = st.selectbox("Etapa (Aves)", etapas_aves, index=etapas_aves.index(etapa_default), key="aves_etapa")

    nutrients_all = get_nutrient_list(df_sel)
    preset = get_stage_preset("Aves", etapa)
    preset_compat = [n for n in preset.keys() if n in nutrients_all]

    preferred_ema, other_ema = _resolve_ema_for_stage_from_preset(etapa, preset, nutrients_all)
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

        st.session_state["aves_req_input"] = {
            n: {
                "min": _normalize_bound(st.session_state.get(f"aves_req_min_{n}", 0)),
                "max": _normalize_bound(st.session_state.get(f"aves_req_max_{n}", 0)),
            }
            for n in selected
        }
        st.rerun()

    selected_nutrients = st.multiselect(
        "Nutrientes a considerar",
        nutrients_all,
        default=st.session_state.get("aves_nutrients_selected", preset_compat[: min(14, len(preset_compat))]),
        key="aves_nutrients_selected",
    )

    effective_nutrients = list(selected_nutrients)
    if not effective_nutrients:
        return

    current_req_input = st.session_state.get("aves_req_input", {})
    req_input_clean = {}
    for n in effective_nutrients:
        if n in current_req_input:
            req_input_clean[n] = {
                "min": _normalize_bound(current_req_input[n].get("min", 0)),
                "max": _normalize_bound(current_req_input[n].get("max", 0)),
            }
        else:
            req_input_clean[n] = {
                "min": _normalize_bound(st.session_state.get(f"aves_req_min_{n}", preset.get(n, {}).get("min", 0))),
                "max": _normalize_bound(st.session_state.get(f"aves_req_max_{n}", preset.get(n, {}).get("max", 0))),
            }

    st.session_state["aves_req_input"] = req_input_clean
    st.session_state["ingredients_df"] = df_sel.copy()

    if "aves_ratios" not in st.session_state:
        st.session_state["aves_ratios"] = []

    ratios_active = [
        r for r in st.session_state.get("aves_ratios", [])
        if r.get("numerador") in effective_nutrients
        and r.get("denominador") in effective_nutrients
        and r.get("numerador") != r.get("denominador")
        and r.get("operador") in {">=", "<=", "="}
        and _safe_float(r.get("valor", 0), 0) > 0
    ]

    preview = OptimizationAdapter().solve(
        ingredients_df=df_sel,
        nutrient_list=effective_nutrients,
        requirements=req_input_clean,
        limits={"min": min_limits, "max": max_limits},
        selected_species="Aves",
        selected_stage=etapa,
        ratios=ratios_active,
    )

    rows = []
    for n in effective_nutrients:
        mn = req_input_clean[n]["min"]
        mx = req_input_clean[n]["max"]
        if preview.get("success"):
            obt = float(preview.get("nutritional_values", {}).get(n, 0) or 0)
            prog_txt, _ = _render_progress(mn, mx, obt)
            sp = preview.get("shadow_prices", {}).get(n, None) if mn > 0 else None
            imp_txt, imp_val = _shadow_impact_pct(sp, preview.get("cost", 0))
            marg = _marginal_cost_ton(sp)
            imp_cls = _impact_class(imp_val)
            ing_assoc = _get_limiting_ing(n, preview.get("diet", {}), df_sel)
        else:
            obt, prog_txt, imp_txt, marg, imp_cls, ing_assoc = None, "No factible", "—", "—", "—", "—"

        rows.append({
            "Nutriente": n,
            "Min": mn,
            "Max": mx if mx > 0 else None,
            "Obtenido": obt,
            "% Logrado": prog_txt,
            "Impacto relativo": imp_txt,
            "Costo marginal": marg,
            "Impacto": imp_cls,
            "Ing. asociado": ing_assoc,
        })

    with st.form("aves_req_form_unified"):
        df_edit = st.data_editor(pd.DataFrame(rows), use_container_width=True, hide_index=True, key="aves_req_editor_unified")
        save_req_btn = st.form_submit_button("Guardar cambios en requerimientos", type="primary")

    if save_req_btn:
        new_req_input = {}
        for _, r in df_edit.iterrows():
            n = r["Nutriente"]
            new_req_input[n] = {
                "min": _normalize_bound(r["Min"]) if pd.notna(r["Min"]) else 0,
                "max": _normalize_bound(r["Max"]) if pd.notna(r["Max"]) else 0,
            }
            st.session_state[f"aves_req_min_{n}"] = new_req_input[n]["min"]
            st.session_state[f"aves_req_max_{n}"] = new_req_input[n]["max"]

        st.session_state["aves_req_input"] = new_req_input
        st.rerun()

    req_input_clean = {
        n: {
            "min": _normalize_bound(st.session_state.get("aves_req_input", {}).get(n, {}).get("min", 0)),
            "max": _normalize_bound(st.session_state.get("aves_req_input", {}).get(n, {}).get("max", 0)),
        }
        for n in effective_nutrients
    }

    errors, warnings = _validate_before_solve(df_sel, effective_nutrients, req_input_clean, min_limits, max_limits, ratios_active)
    if warnings:
        for w in warnings:
            st.warning(w)
    if errors:
        for e in errors:
            st.error(e)
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Verificar factibilidad preliminar", key="aves_precheck"):
            pre = OptimizationAdapter().solve(
                ingredients_df=df_sel,
                nutrient_list=effective_nutrients,
                requirements=req_input_clean,
                limits={"min": min_limits, "max": max_limits},
                selected_species="Aves",
                selected_stage=etapa,
                ratios=ratios_active,
            )
            st.success("Factible") if pre.get("success") else st.error(pre.get("message", "No factible"))

    with col2:
        if st.button("Formular dieta óptima", type="primary", key="aves_solve_final"):
            result = OptimizationAdapter().solve(
                ingredients_df=df_sel,
                nutrient_list=effective_nutrients,
                requirements=req_input_clean,
                limits={"min": min_limits, "max": max_limits},
                selected_species="Aves",
                selected_stage=etapa,
                ratios=ratios_active,
            )
            st.session_state["last_result_aves"] = result
            st.session_state["ingredients_df"] = df_sel.copy()
            st.session_state["aves_last_inputs"] = {
                "selected_ingredients": list(df_sel["Ingrediente"].astype(str).tolist()),
                "limits": {"min": min_limits, "max": max_limits},
                "requirements": req_input_clean,
                "ratios": ratios_active,
                "stage": etapa,
            }
            st.success("Formulación exitosa") if result.get("success") else st.error(result.get("message", "No se pudo formular"))


def render_results_tab():
    from src.ui.pages.results import render as render_global_results
    render_global_results()


def render_charts_tab():
    from src.ui.pages.charts import render as render_global_charts
    render_global_charts()


def render_report_tab():
    st.subheader("Informe final")
    result = st.session_state.get("last_result_aves")
    if not result:
        st.info("No hay corrida para reportar.")
        return

    if not result.get("success"):
        st.error("Última corrida no factible.")
        st.write(result.get("message", "Sin detalle"))
        return

    st.success("Informe rápido generado")
    st.write(f"**Costo total (100kg):** ${result.get('cost', 0):.2f}")
    st.write(f"**Ingredientes activos:** {len(result.get('diet', {}))}")

    # --- Escenario técnico descargable ---
    render_section("Escenario técnico", "Exporta un escenario estandarizado compatible para comparación futura.")

    last_inputs = st.session_state.get("aves_last_inputs", {})
    ingredients_df = st.session_state.get("ingredients_df", pd.DataFrame())

    scenario_name = st.text_input(
        "Nombre del escenario",
        value=f"Aves_{last_inputs.get('stage', 'Etapa')}",
        key="aves_report_scenario_name",
    )

    if st.button("Construir escenario técnico", key="aves_build_scenario_btn"):
        payload = build_scenario_payload(
            scenario_name=scenario_name,
            species="Aves",
            stage=last_inputs.get("stage", "Sin etapa"),
            user=st.session_state.get("usuario", "usuario"),
            ingredients_df=ingredients_df,
            selected_ingredients=last_inputs.get("selected_ingredients", []),
            limits=last_inputs.get("limits", {"min": {}, "max": {}}),
            requirements=last_inputs.get("requirements", {}),
            ratios=last_inputs.get("ratios", []),
            result=result,
            app_version="1.0.0",
            solver_engine="DietFormulator",
            solver_version="1.0.0",
        )

        st.session_state["aves_built_scenario_payload"] = payload
        st.success("Escenario técnico construido correctamente.")

    payload = st.session_state.get("aves_built_scenario_payload")
    if payload:
        scenario_json = scenario_to_json(payload)
        st.download_button(
            label="Descargar escenario (.json)",
            data=scenario_json,
            file_name=f"{payload.get('scenario_name', 'scenario')}.json",
            mime="application/json",
            key="aves_download_scenario_json_btn",
        )

        with st.expander("Previsualizar escenario técnico (JSON)", expanded=False):
            st.code(scenario_json, language="json")


def render():
    st.title("Formulador · Aves")
    t1, t2, t3, t4 = st.tabs(["Formulación", "Resultados", "Gráficos", "Informe final"])
    with t1:
        render_formulation_aves()
    with t2:
        render_results_tab()
    with t3:
        render_charts_tab()
    with t4:
        render_report_tab()
