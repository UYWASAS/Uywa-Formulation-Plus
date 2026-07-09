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

from src.core.scenarios.build_scenario import build_scenario_payload, scenario_to_json
from src.core.reports.client_report_html import build_client_report_html
from src.core.scenarios.export_scenario import export_scenario_zip

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

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


def _create_ingredients_csv(df_selected: pd.DataFrame) -> str:
    return df_selected.to_csv(index=False)


def _load_ingredients_csv(uploaded_file, df_macro):
    errors = []
    try:
        df_loaded = pd.read_csv(uploaded_file)
        if "Ingrediente" not in df_loaded.columns:
            return None, None, ["El CSV debe contener columna 'Ingrediente'."]

        requested = df_loaded["Ingrediente"].dropna().astype(str).tolist()
        available = set(df_macro["Ingrediente"].dropna().astype(str).tolist())

        found = [i for i in requested if i in available]
        missing = [i for i in requested if i not in available]

        if missing:
            errors.append("Ingredientes no encontrados en matriz activa: " + ", ".join(missing))

        df_filtered = df_macro[df_macro["Ingrediente"].isin(found)].copy()
        return found, df_filtered, errors
    except Exception as e:
        return None, None, [f"Error cargando CSV de ingredientes: {str(e)}"]


def _create_requirements_csv(species, stage, req_data: dict) -> str:
    buf = io.StringIO()
    buf.write("especie,etapa,nutriente,min_value,max_value\n")
    for n, v in req_data.items():
        mn = _safe_float(v.get("min", 0), 0)
        mx = _safe_float(v.get("max", 0), 0)
        buf.write(f"{species},{stage},{n},{mn},{mx}\n")
    return buf.getvalue()


def _load_requirements_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        required = {"nutriente", "min_value"}
        if not required.issubset(set(df.columns)):
            return None, "El CSV de requerimientos debe contener columnas: nutriente, min_value (max_value opcional)."

        req = {}
        nutrients = []
        for _, r in df.iterrows():
            n = str(r.get("nutriente", "")).strip()
            if not n:
                continue
            mn = _normalize_bound(r.get("min_value", 0))
            mx = _normalize_bound(r.get("max_value", 0)) if "max_value" in df.columns else 0.0
            req[n] = {"min": mn, "max": mx}
            nutrients.append(n)

        return {"requirements": req, "nutrients": nutrients}, None
    except Exception as e:
        return None, f"Error cargando requerimientos: {str(e)}"


def _create_project_zip_export(
    ingredientes_df,
    req_data,
    etapa,
    usuario,
    min_limits=None,
    max_limits=None,
    ratios=None,
    nutrientes_seleccionados=None
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

        zf.writestr(
            "ingredient_limits.json",
            json.dumps({"min_limits": min_limits, "max_limits": max_limits}, indent=2, ensure_ascii=False),
        )
        zf.writestr("ratios.json", json.dumps(ratios, indent=2, ensure_ascii=False))
        zf.writestr("project_metadata.json", json.dumps({
            "especie": "Aves",
            "etapa": etapa,
            "usuario": usuario,
            "fecha": date.today().isoformat(),
            "version": "aves-modular-full-2.0",
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


# -------------------------------------------------------------------
# Formulación
# -------------------------------------------------------------------

def render_formulation_aves():
    st.subheader("Formulación")

    # ------------------- CARGAR PROYECTO ZIP -------------------
    with st.expander("Cargar proyecto completo UYWA (.zip)", expanded=False):
        up_zip = st.file_uploader("Subir ZIP de proyecto", type=["zip"], key="aves_project_zip_upload")
        if up_zip is not None and st.button("Restaurar proyecto", key="aves_restore_zip_btn"):
            data, errors = _load_project_zip(up_zip)
            if errors:
                render_card("Error al restaurar proyecto", " | ".join(errors), variant="danger")
            else:
                st.session_state["aves_loaded_ingredients_df"] = data["ingredients_df"].copy()
                st.session_state["ingredients_df"] = data["ingredients_df"].copy()

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
                        nutr_loaded.append(n)

                st.session_state["aves_req_input"] = req_data
                st.session_state["aves_nutrients_selected"] = nutr_loaded
                st.session_state["aves_min_limits_loaded"] = data["limits"].get("min_limits", {})
                st.session_state["aves_max_limits_loaded"] = data["limits"].get("max_limits", {})
                st.session_state["aves_ratios"] = data.get("ratios", [])

                idf = data["ingredients_df"]
                if "Ingrediente" in idf.columns:
                    st.session_state["aves_ingredientes_sel"] = idf["Ingrediente"].dropna().astype(str).tolist()

                st.success("Proyecto restaurado correctamente.")
                st.rerun()

    # ------------------- MATRIZ -------------------
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

    # ------------------- SELECCIÓN DE INGREDIENTES -------------------
    render_section("Selección de ingredientes", "Selecciona ingredientes y límites de inclusión.")
    ing_all = df["Ingrediente"].dropna().tolist()
    pre = st.session_state.get("aves_ingredientes_sel", ing_all[: min(25, len(ing_all))])
    ingredientes_sel = st.multiselect(
        "Ingredientes a usar",
        ing_all,
        default=[i for i in pre if i in ing_all],
        key="aves_ingredientes_sel"
    )
    if not ingredientes_sel:
        return

    df_sel = df[df["Ingrediente"].isin(ingredientes_sel)].copy()
    with st.expander("Ver o editar composición de ingredientes seleccionados", expanded=False):
        df_sel = st.data_editor(df_sel, use_container_width=True, num_rows="dynamic", key="aves_df_editor")

    # -------- Descargar / Cargar matriz seleccionada --------
    with st.expander("Descargar o cargar matriz de ingredientes", expanded=False):
        c1, c2 = st.columns(2)

        with c1:
            if st.button("Preparar descarga de matriz actual", key="aves_btn_prepare_matrix_csv"):
                csv_content = _create_ingredients_csv(df_sel)
                st.download_button(
                    label="Descargar matriz seleccionada (CSV)",
                    data=csv_content,
                    file_name=f"aves_matriz_seleccionada_{date.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="aves_download_matrix_csv"
                )

        with c2:
            up_ing_csv = st.file_uploader(
                "Cargar matriz guardada (CSV)",
                type=["csv"],
                key="aves_upload_matrix_saved_csv"
            )
            if up_ing_csv is not None and st.button("Aplicar matriz cargada", key="aves_apply_loaded_matrix_csv"):
                found, df_loaded, errs = _load_ingredients_csv(up_ing_csv, df)
                if errs:
                    for e in errs:
                        st.warning(e)
                if found:
                    st.session_state["aves_ingredientes_sel"] = found
                    st.success(f"Se cargaron {len(found)} ingredientes.")
                    st.rerun()

    # ------------------- LÍMITES -------------------
    ing_limit = st.multiselect(
        "Ingredientes con límites",
        ingredientes_sel,
        default=st.session_state.get("aves_ingredientes_limitar", []),
        key="aves_ingredientes_limitar"
    )

    min_limits, max_limits = {}, {}
    min_loaded = st.session_state.get("aves_min_limits_loaded", {})
    max_loaded = st.session_state.get("aves_max_limits_loaded", {})

    for ing in ing_limit:
        c = st.columns([2, 1, 1])
        c[0].write(ing)
        max_v = c[1].number_input(
            "max", min_value=0.0, max_value=100.0,
            value=float(max_loaded.get(ing, 100.0)),
            key=f"aves_max_{ing}", label_visibility="collapsed"
        )
        min_v = c[2].text_input(
            "min", value=str(min_loaded.get(ing, "")),
            key=f"aves_min_{ing}", label_visibility="collapsed"
        )
        min_limits[ing] = _safe_float(min_v, 0)
        max_limits[ing] = _safe_float(max_v, 0)

    # ------------------- REQUERIMIENTOS -------------------
    render_section("Requerimientos nutricionales", "Preset + selección libre de nutrientes detectados en la matriz actual.")

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

    nutrients_all = get_nutrient_list(df_sel)  # <-- TODOS los nutrientes de la matriz
    preset = get_stage_preset("Aves", etapa)
    preset_compat = [n for n in preset.keys() if n in nutrients_all]

    if st.button("Cargar preset completo", key="aves_load_preset"):
        st.session_state["aves_nutrients_selected"] = preset_compat.copy()
        req_data = {}
        for n in preset_compat:
            req_data[n] = {
                "min": _normalize_bound(preset.get(n, {}).get("min", 0)),
                "max": _normalize_bound(preset.get(n, {}).get("max", 0)),
            }
        st.session_state["aves_req_input"] = req_data
        st.success("Preset cargado. Puedes agregar más nutrientes manualmente.")
        st.rerun()

    # CARGA DE REQUERIMIENTOS CSV
    up_req = st.file_uploader("Cargar requerimientos desde archivo CSV", type=["csv"], key="aves_upload_req_csv")
    if up_req is not None and st.button("Aplicar requerimientos CSV", key="aves_apply_req_csv"):
        req_loaded, err = _load_requirements_csv(up_req)
        if err:
            st.error(err)
        else:
            # solo mantener nutrientes que existan en matriz actual
            req_filtered = {
                n: v for n, v in req_loaded["requirements"].items()
                if n in nutrients_all
            }
            st.session_state["aves_req_input"] = req_filtered
            st.session_state["aves_nutrients_selected"] = list(req_filtered.keys())
            st.success(f"Requerimientos cargados: {len(req_filtered)} nutrientes aplicados.")
            st.rerun()

    selected_nutrients = st.multiselect(
        "Nutrientes a considerar",
        nutrients_all,  # <-- abierto a todos los nutrientes detectados
        default=[n for n in st.session_state.get("aves_nutrients_selected", preset_compat[:min(14, len(preset_compat))]) if n in nutrients_all],
        key="aves_nutrients_selected",
        help="El preset solo preselecciona. Aquí puedes usar cualquier nutriente presente en la matriz actual."
    )

    if not selected_nutrients:
        st.info("Selecciona al menos un nutriente.")
        return

    current_req_input = st.session_state.get("aves_req_input", {})
    req_input_clean = {}
    for n in selected_nutrients:
        req_input_clean[n] = {
            "min": _normalize_bound(current_req_input.get(n, {}).get("min", 0)),
            "max": _normalize_bound(current_req_input.get(n, {}).get("max", 0)),
        }
    st.session_state["aves_req_input"] = req_input_clean

    # Tabla editable min/max
    req_rows = []
    for n in selected_nutrients:
        req_rows.append({
            "Nutriente": n,
            "Min": req_input_clean[n]["min"],
            "Max": req_input_clean[n]["max"],
        })

    with st.form("aves_req_form"):
        df_req_edit = st.data_editor(pd.DataFrame(req_rows), use_container_width=True, hide_index=True, key="aves_req_editor")
        save_req_btn = st.form_submit_button("Guardar cambios en requerimientos", type="primary")

    if save_req_btn:
        new_req = {}
        for _, r in df_req_edit.iterrows():
            n = r["Nutriente"]
            new_req[n] = {
                "min": _normalize_bound(r["Min"]) if pd.notna(r["Min"]) else 0.0,
                "max": _normalize_bound(r["Max"]) if pd.notna(r["Max"]) else 0.0,
            }
        st.session_state["aves_req_input"] = new_req
        st.success("Requerimientos actualizados.")

    # Descarga requerimientos editados
    req_csv = _create_requirements_csv("Aves", etapa, st.session_state.get("aves_req_input", {}))
    st.download_button(
        "Descargar requerimientos editados (CSV)",
        data=req_csv,
        file_name=f"aves_requerimientos_{etapa.replace(' ','_')}_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="aves_download_req_csv"
    )

    # Ratios
    if "aves_ratios" not in st.session_state:
        st.session_state["aves_ratios"] = []

    with st.expander("Ratios entre nutrientes", expanded=False):
        if len(selected_nutrients) >= 2:
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            num = c1.selectbox("Numerador", selected_nutrients, key="aves_ratio_num")
            den_opts = [n for n in selected_nutrients if n != num]
            den = c2.selectbox("Denominador", den_opts, key="aves_ratio_den")
            op = c3.selectbox("Operador", [">=", "<=", "="], key="aves_ratio_op")
            val = c4.number_input("Valor", min_value=0.0, value=1.0, step=0.01, key="aves_ratio_val")
            if st.button("Agregar ratio", key="aves_ratio_add"):
                st.session_state["aves_ratios"].append({
                    "numerador": num, "denominador": den, "operador": op, "valor": float(val)
                })
                st.rerun()

        if st.session_state["aves_ratios"]:
            for i, r in enumerate(st.session_state["aves_ratios"]):
                cc1, cc2 = st.columns([6, 1])
                cc1.write(f"{r['numerador']} / {r['denominador']} {r['operador']} {r['valor']}")
                if cc2.button("Eliminar", key=f"aves_ratio_del_{i}"):
                    st.session_state["aves_ratios"].pop(i)
                    st.rerun()

    # ------------------- VALIDACIÓN MÍNIMA -------------------
    if "Ingrediente" not in df_sel.columns or "precio" not in df_sel.columns:
        st.error("La matriz seleccionada debe incluir columnas 'Ingrediente' y 'precio'.")
        return

    smin = sum(_safe_float(min_limits.get(i, 0), 0) for i in min_limits.keys())
    if smin > 100:
        st.error(f"La suma de mínimos por ingrediente es {smin:.2f}% (>100%).")
        return

    active_restr = 0
    for n in selected_nutrients:
        mn = _safe_float(st.session_state["aves_req_input"].get(n, {}).get("min", 0), 0)
        mx = _safe_float(st.session_state["aves_req_input"].get(n, {}).get("max", 0), 0)
        if mx > 0 and mn > mx:
            st.error(f"Nutriente '{n}' tiene mínimo mayor que máximo.")
            return
        if mn > 0 or mx > 0:
            active_restr += 1

    if active_restr == 0:
        st.error("No hay restricciones activas (min/max > 0).")
        return

    # ------------------- SOLVER -------------------
    ratios_active = [
        r for r in st.session_state.get("aves_ratios", [])
        if r.get("numerador") in selected_nutrients
        and r.get("denominador") in selected_nutrients
        and r.get("numerador") != r.get("denominador")
        and r.get("operador") in {">=", "<=", "="}
        and _safe_float(r.get("valor", 0), 0) > 0
    ]

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Verificar factibilidad preliminar", key="aves_precheck"):
            pre = OptimizationAdapter().solve(
                ingredients_df=df_sel,
                nutrient_list=selected_nutrients,
                requirements=st.session_state["aves_req_input"],
                limits={"min": min_limits, "max": max_limits},
                selected_species="Aves",
                selected_stage=etapa,
                ratios=ratios_active,
            )
            if pre.get("success"):
                st.success("Factible.")
            else:
                st.error(pre.get("message", "No factible."))

    with col2:
        if st.button("Formular dieta óptima", type="primary", key="aves_solve_final"):
            result = OptimizationAdapter().solve(
                ingredients_df=df_sel,
                nutrient_list=selected_nutrients,
                requirements=st.session_state["aves_req_input"],
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
                "requirements": st.session_state["aves_req_input"],
                "ratios": ratios_active,
                "stage": etapa,
            }

            if result.get("success"):
                st.success("Formulación exitosa.")
            else:
                st.error(result.get("message", "No se pudo formular."))

    # ------------------- GUARDAR PROYECTO ZIP -------------------
    st.markdown("---")
    render_section("Guardar proyecto completo", "Descarga ZIP con ingredientes, requerimientos, límites, ratios y metadatos.")

    project_name = st.text_input(
        "Nombre del proyecto",
        value=f"Aves_{etapa}_{date.today().strftime('%Y%m%d')}".replace(" ", "_"),
        key="aves_project_name"
    )

    if st.button("Preparar ZIP", key="aves_prepare_project_zip", use_container_width=True):
        zip_buffer = _create_project_zip_export(
            ingredientes_df=df_sel,
            req_data=st.session_state.get("aves_req_input", {}),
            etapa=etapa,
            usuario=st.session_state.get("usuario", "usuario"),
            min_limits=min_limits,
            max_limits=max_limits,
            ratios=ratios_active,
            nutrientes_seleccionados=selected_nutrients,
        )
        st.download_button(
            "Descargar proyecto completo (ZIP)",
            data=zip_buffer,
            file_name=f"{project_name}.zip",
            mime="application/zip",
            key="aves_download_project_zip",
        )


# -------------------------------------------------------------------
# Tabs delegadas
# -------------------------------------------------------------------

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

    st.success("Informe listo para exportar")
    cost_100kg = result.get("cost", 0)
    st.write(f"**Costo total (100kg):** ${cost_100kg:.2f}")
    st.write(f"**Costo/kg:** ${cost_100kg/100:.2f}")
    st.write(f"**Costo/ton:** ${cost_100kg/100*1000:,.2f}")
    st.write(f"**Ingredientes activos:** {len(result.get('diet', {}))}")

    render_section("Entregables", "Descarga informe cliente (HTML) y paquete técnico (ZIP/JSON).")

    last_inputs = st.session_state.get("aves_last_inputs", {})
    ingredients_df = st.session_state.get("ingredients_df", None)
    usuario = st.session_state.get("usuario", "usuario")

    scenario_name = st.text_input(
        "Nombre del escenario",
        value=f"Aves_{last_inputs.get('stage', 'Etapa')}_{usuario}",
        key="aves_report_scenario_name",
    )

    if st.button("Construir entregables", key="aves_build_entregables_btn", type="primary", use_container_width=True):
        try:
            payload = build_scenario_payload(
                scenario_name=scenario_name,
                species="Aves",
                stage=last_inputs.get("stage", "Sin etapa"),
                user=usuario,
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
            html_content = build_client_report_html(payload)

            st.session_state["aves_scenario_payload"] = payload
            st.session_state["aves_report_html"] = html_content
            st.success("✅ Entregables construidos correctamente.")
        except Exception as e:
            render_card("Error construyendo entregables", str(e), variant="danger")
            return

    payload = st.session_state.get("aves_scenario_payload")
    html_content = st.session_state.get("aves_report_html")

    if payload and html_content:
        c1, c2 = st.columns(2)

        with c1:
            zip_buffer = export_scenario_zip(payload, html_content, payload.get("scenario_name"))
            st.download_button(
                label="📦 Descargar entregables (ZIP)",
                data=zip_buffer,
                file_name=f"{payload.get('scenario_name', 'escenario')}.zip",
                mime="application/zip",
                key="aves_download_entregables_zip",
                use_container_width=True,
            )

        with c2:
            st.download_button(
                label="📄 Descargar informe (HTML)",
                data=html_content,
                file_name=f"{payload.get('scenario_name', 'informe')}.html",
                mime="text/html",
                key="aves_download_informe_html",
                use_container_width=True,
            )

        with st.expander("🔧 Opciones avanzadas (técnico / comparación)", expanded=False):
            st.caption("El JSON técnico se usa para comparación entre dietas y análisis profundos.")
            scenario_json = scenario_to_json(payload)

            st.download_button(
                label="📋 Descargar JSON técnico",
                data=scenario_json,
                file_name=f"{payload.get('scenario_name', 'scenario')}.json",
                mime="application/json",
                key="aves_download_scenario_json",
                use_container_width=True,
            )

            if st.checkbox("Ver JSON técnico", key="aves_show_json_checkbox"):
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
