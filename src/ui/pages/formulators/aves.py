import os
import io
from datetime import date

import pandas as pd
import streamlit as st

from src.core.io.data_access import load_ingredients, get_nutrient_list
from src.core.formulation.presets import get_stage_preset
from src.adapters.optimization_adapter import OptimizationAdapter

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.ui.components.tables import render_table


# ----------------------------
# Helpers locales
# ----------------------------
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
    # 1) upload explícito
    if uploaded_file is not None:
        df = load_ingredients(uploaded_file)
        if df is not None and not df.empty:
            return df.copy()

    # 2) sesión (por si luego agregas ZIP restore)
    cached = st.session_state.get("aves_loaded_ingredients_df")
    if cached is not None and not cached.empty:
        return cached.copy()

    # 3) defaults del repo (raíz/data-files)
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

    # 4) fallback nativo
    return load_ingredients(uploaded_file)


def _validate_before_solve(df_sel, nutrients, req_input, min_limits, max_limits, ratios):
    errors = []
    warnings = []

    if df_sel is None or df_sel.empty:
        errors.append("No hay ingredientes seleccionados para formular.")
        return errors, warnings

    if "Ingrediente" not in df_sel.columns:
        errors.append("La matriz no contiene columna 'Ingrediente'.")
    if "precio" not in df_sel.columns:
        errors.append("La matriz no contiene columna 'precio'.")

    if not nutrients:
        errors.append("No hay nutrientes seleccionados.")

    # suma mínimos ingredientes
    smin = sum(_safe_float(min_limits.get(i, 0), 0) for i in df_sel["Ingrediente"].tolist())
    if smin > 100:
        errors.append(f"La suma de mínimos por ingrediente es {smin:.2f}% (>100%).")

    # reqs activos
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

    # ratios básicos
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


def render():
    st.title("Formulador · Aves")
    st.caption("Flujo avanzado: matriz, límites, requerimientos, ratios, precheck y formulación final.")

    # ----------------------------
    # 1) Carga matriz
    # ----------------------------
    render_section("Matriz de ingredientes", "Carga manual o usa matriz por defecto en data-files/.")

    up = st.file_uploader(
        "Matriz de ingredientes (.csv/.xlsx)",
        type=["csv", "xlsx"],
        key="aves_matriz_upload",
    )

    df = _load_ingredients_robust(up)
    if df is None or df.empty:
        render_card(
            "Sin matriz activa",
            "No se encontró matriz. Sube archivo o agrega data-files/matriz_ingredientes.csv(xlsx).",
            variant="warning",
        )
        return

    if "Ingrediente" not in df.columns or "precio" not in df.columns:
        render_card(
            "Formato inválido",
            "La matriz debe contener columnas 'Ingrediente' y 'precio'.",
            variant="danger",
        )
        return

    # saneo
    df = df.copy()
    df["Ingrediente"] = df["Ingrediente"].astype(str)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)

    render_card("Matriz activa", f"Ingredientes disponibles: {len(df)}", variant="success")

    # ----------------------------
    # 2) Selección ingredientes
    # ----------------------------
    render_section("Selección de ingredientes")

    ing_all = df["Ingrediente"].dropna().tolist()
    pre = st.session_state.get("aves_ingredientes_sel", ing_all[: min(25, len(ing_all))])

    ingredientes_sel = st.multiselect(
        "Ingredientes a usar",
        options=ing_all,
        default=[i for i in pre if i in ing_all],
        key="aves_ingredientes_sel",
    )

    if not ingredientes_sel:
        render_card("Selección vacía", "Elige al menos un ingrediente.", variant="warning")
        return

    df_sel = df[df["Ingrediente"].isin(ingredientes_sel)].copy()

    with st.expander("Ver/editar composición de ingredientes seleccionados", expanded=False):
        df_sel = st.data_editor(
            df_sel,
            use_container_width=True,
            num_rows="dynamic",
            key="aves_df_editor",
        )

    # ----------------------------
    # 3) Límites ingredientes
    # ----------------------------
    render_section("Límites de inclusión (%)", "Define min/max solo donde quieras control.")

    ing_limit = st.multiselect(
        "Ingredientes con límites",
        options=ingredientes_sel,
        default=st.session_state.get("aves_ingredientes_limitar", []),
        key="aves_ingredientes_limitar",
    )

    min_limits = {}
    max_limits = {}

    if ing_limit:
        with st.expander("Editar límites por ingrediente", expanded=True):
            h = st.columns([2, 1, 1])
            h[0].markdown("**Ingrediente**")
            h[1].markdown("**Máximo (%)**")
            h[2].markdown("**Mínimo (%)**")

            for ing in ing_limit:
                c = st.columns([2, 1, 1])
                c[0].write(ing)
                max_v = c[1].number_input(
                    "max",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.get(f"aves_max_{ing}", 100.0)),
                    key=f"aves_max_{ing}",
                    label_visibility="collapsed",
                )
                min_v_txt = c[2].text_input(
                    "min",
                    value=str(st.session_state.get(f"aves_min_{ing}", "")),
                    key=f"aves_min_{ing}",
                    label_visibility="collapsed",
                    placeholder="0",
                )

                min_limits[ing] = _safe_float(min_v_txt, 0)
                max_limits[ing] = _safe_float(max_v, 0)

    # ----------------------------
    # 4) Etapa + nutrientes + preset
    # ----------------------------
    render_section("Requerimientos nutricionales")

    etapas_aves = [
        "Broiler Iniciación",
        "Broiler Crecimiento",
        "Broiler Cebo",
        "Broiler Acabado",
        "Pollita Recría 0-5",
        "Pollita Recría 5-10",
        "Pollita Recría 10-17",
        "Pollita Inicio Puesta",
        "Ponedora Pre-Pico",
        "Ponedora Inicio Postura",
        "Ponedora Final Postura",
        "Ponedora Problemas Cascara",
    ]

    etapa = st.selectbox("Etapa (Aves)", etapas_aves, key="aves_etapa")

    nutrients_all = get_nutrient_list(df_sel if not df_sel.empty else df)
    preset = get_stage_preset("Aves", etapa)
    preset_compat = [n for n in preset.keys() if n in nutrients_all]

    cbtn1, cbtn2 = st.columns([1, 2])
    with cbtn1:
        if st.button("Cargar preset completo", key="aves_cargar_preset"):
            st.session_state["aves_nutrients_selected"] = preset_compat
            for n in preset_compat:
                st.session_state[f"aves_req_min_{n}"] = float(preset.get(n, {}).get("min", 0) or 0)
                st.session_state[f"aves_req_max_{n}"] = float(preset.get(n, {}).get("max", 0) or 0)
            st.success(f"Preset cargado: {len(preset_compat)} nutrientes compatibles.")

    selected_nutrients = st.multiselect(
        "Nutrientes a considerar",
        options=nutrients_all,
        default=st.session_state.get("aves_nutrients_selected", preset_compat[: min(14, len(preset_compat))]),
        key="aves_nutrients_selected",
    )

    if not selected_nutrients:
        st.info("Selecciona nutrientes para continuar.")
        return

    # ----------------------------
    # 5) Tabla editable min/max
    # ----------------------------
    render_section("Tabla de requerimientos", "Edita Min y Max; el resto se calcula al formular.")

    req_rows = []
    for n in selected_nutrients:
        req_rows.append(
            {
                "Nutriente": n,
                "Min": float(st.session_state.get(f"aves_req_min_{n}", preset.get(n, {}).get("min", 0) or 0)),
                "Max": float(st.session_state.get(f"aves_req_max_{n}", preset.get(n, {}).get("max", 0) or 0)),
            }
        )

    req_df = st.data_editor(
        pd.DataFrame(req_rows),
        use_container_width=True,
        hide_index=True,
        key="aves_req_editor",
        column_config={
            "Nutriente": st.column_config.TextColumn("Nutriente", disabled=True),
            "Min": st.column_config.NumberColumn("Min", min_value=0.0, format="%.4f"),
            "Max": st.column_config.NumberColumn("Max", min_value=0.0, format="%.4f"),
        },
    )

    req_input = {}
    for _, r in req_df.iterrows():
        n = r["Nutriente"]
        mn = _normalize_bound(r["Min"])
        mx = _normalize_bound(r["Max"])
        st.session_state[f"aves_req_min_{n}"] = mn
        st.session_state[f"aves_req_max_{n}"] = mx
        req_input[n] = {"min": mn, "max": mx}

    # ----------------------------
    # 6) Ratios
    # ----------------------------
    render_section("Ratios entre nutrientes (opcional)")

    if "aves_ratios" not in st.session_state:
        st.session_state["aves_ratios"] = []

    if len(selected_nutrients) >= 2:
        ex = st.expander("Agregar ratio", expanded=False)
        with ex:
            c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
            num = c1.selectbox("Numerador", selected_nutrients, key="aves_ratio_num")
            den_opts = [x for x in selected_nutrients if x != num]
            den = c2.selectbox("Denominador", den_opts, key="aves_ratio_den")
            op = c3.selectbox("Op", [">=", "<=", "="], key="aves_ratio_op")
            val = c4.number_input("Valor", min_value=0.0, value=1.0, step=0.01, key="aves_ratio_val")

            if st.button("Agregar ratio", key="aves_ratio_add"):
                st.session_state["aves_ratios"].append(
                    {"numerador": num, "denominador": den, "operador": op, "valor": float(val)}
                )
                st.rerun()

    if st.session_state["aves_ratios"]:
        with st.expander("Ratios activos", expanded=True):
            to_delete = []
            for i, r in enumerate(st.session_state["aves_ratios"]):
                cx1, cx2 = st.columns([6, 1])
                cx1.write(f"{r['numerador']} / {r['denominador']} {r['operador']} {r['valor']}")
                if cx2.button("Eliminar", key=f"aves_ratio_del_{i}"):
                    to_delete.append(i)
            for i in sorted(to_delete, reverse=True):
                st.session_state["aves_ratios"].pop(i)
            if to_delete:
                st.rerun()

    ratios = st.session_state["aves_ratios"]

    # ----------------------------
    # 7) Validación + precheck + formular
    # ----------------------------
    render_section("Verificación y formulación final")

    errors, warnings = _validate_before_solve(
        df_sel=df_sel,
        nutrients=selected_nutrients,
        req_input=req_input,
        min_limits=min_limits,
        max_limits=max_limits,
        ratios=ratios,
    )

    if warnings:
        with st.expander("Advertencias", expanded=False):
            for w in warnings:
                st.warning(w)

    if errors:
        render_card("No se puede formular todavía", "Corrige los errores listados.", variant="danger")
        for e in errors:
            st.write(f"- {e}")
        return

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Verificar factibilidad preliminar", use_container_width=True, key="aves_precheck"):
            adapter = OptimizationAdapter()
            pre = adapter.solve(
                ingredients_df=df_sel,
                nutrient_list=selected_nutrients,
                requirements=req_input,
                limits={"min": min_limits, "max": max_limits},
                selected_species="Aves",
                selected_stage=etapa,
                ratios=ratios,
            )
            if pre.get("success"):
                render_card("Factibilidad", "No se detectó bloqueo preliminar crítico.", variant="success")
            else:
                render_card("Posible conflicto", pre.get("message", "Sin detalle"), variant="warning")
                diag = pre.get("infeasibility_diagnostics", [])
                if diag:
                    render_table(pd.DataFrame(diag))

    with col_b:
        if st.button("Formular dieta óptima", type="primary", use_container_width=True, key="aves_solve"):
            adapter = OptimizationAdapter()
            result = adapter.solve(
                ingredients_df=df_sel,
                nutrient_list=selected_nutrients,
                requirements=req_input,
                limits={"min": min_limits, "max": max_limits},
                selected_species="Aves",
                selected_stage=etapa,
                ratios=ratios,
            )

            # compatibilidad modular + legacy
            st.session_state["last_result_aves"] = result
            st.session_state["req_input"] = req_input
            st.session_state["nutrientes_seleccionados"] = selected_nutrients
            st.session_state["ingredients_df"] = df_sel.copy()

            if result.get("success"):
                st.session_state["last_diet"] = result.get("diet", {})
                st.session_state["last_cost"] = result.get("cost", 0)
                st.session_state["last_nutritional_values"] = result.get("nutritional_values", {})
                st.session_state["last_constraint_diagnostics"] = result.get("constraint_diagnostics", {})
                st.session_state["last_infeasibility_diagnostics"] = []
                render_card("Formulación exitosa", "Resultado guardado en Resultados/Gráficos.", variant="success")
            else:
                st.session_state["last_infeasibility_diagnostics"] = result.get("infeasibility_diagnostics", [])
                render_card("No se pudo formular", result.get("message", "Sin detalle"), variant="danger")

    # ----------------------------
    # 8) Vista previa resultado
    # ----------------------------
    result = st.session_state.get("last_result_aves")
    if result:
        st.markdown("---")
        render_section("Vista previa de formulación")

        if result.get("success"):
            diet = result.get("diet", {})
            cost = result.get("cost", 0)

            c1, c2, c3 = st.columns(3)
            with c1:
                render_metric_card("Costo (100 kg)", f"${cost:.2f}", "Salida solver")
            with c2:
                render_metric_card("Costo/kg", f"${(cost/100):.4f}", "Estimado")
            with c3:
                render_metric_card("Ingredientes activos", str(len(diet)), "Con inclusión > 0")

            df_d = pd.DataFrame(list(diet.items()), columns=["Ingrediente", "Inclusión (%)"])
            if not df_d.empty:
                df_d = df_d.sort_values("Inclusión (%)", ascending=False)
                render_table(
                    df_d,
                    column_config={
                        "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.4f")
                    },
                )
        else:
            st.error(result.get("message", "No se pudo formular."))
            diag = result.get("infeasibility_diagnostics", [])
            if diag:
                with st.expander("Diagnóstico preliminar", expanded=False):
                    render_table(pd.DataFrame(diag))

    # ----------------------------
    # 9) Descargar requerimientos editados
    # ----------------------------
    if selected_nutrients and req_input:
        csv_buffer = io.StringIO()
        csv_buffer.write("especie,etapa,nutriente,min_value,max_value\n")
        for n in selected_nutrients:
            csv_buffer.write(
                f"Aves,{etapa},{n},{req_input.get(n, {}).get('min', 0)},{req_input.get(n, {}).get('max', 0)}\n"
            )
        st.download_button(
            "Descargar requerimientos editados (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"requerimientos_aves_{date.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="aves_req_download",
        )
