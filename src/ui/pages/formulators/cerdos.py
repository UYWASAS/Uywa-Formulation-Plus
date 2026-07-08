import streamlit as st
import pandas as pd

from src.core.io.data_access import load_ingredients, get_nutrient_list
from src.core.formulation.presets import get_stage_preset
from src.adapters.optimization_adapter import OptimizationAdapter


CERDOS_ETAPAS = [
    "Adultos - Gestación estándar",
    "Adultos - Lactación estándar",
    "Adultos - Verracos",
    "Lechones - Preiniciador",
    "Lechones - Inicio",
    "Lechones - Crecimiento temprano",
    "Cerdos - Crecimiento 20-60 kg",
    "Cerdos - Engorde 60-100 kg",
    "Cerdos - Acabado >100 kg",
]


def render():
    st.title("Formulador · Cerdos")
    st.caption("Módulo modular conectado al mismo motor de cálculo (DietFormulator).")

    up = st.file_uploader(
        "Matriz de ingredientes (.csv/.xlsx)",
        type=["csv", "xlsx"],
        key="cerdos_matriz_upload",
    )

    df = load_ingredients(up)
    if df is None or df.empty:
        st.info("Carga una matriz para comenzar.")
        return

    if "Ingrediente" not in df.columns or "precio" not in df.columns:
        st.error("La matriz debe contener columnas 'Ingrediente' y 'precio'.")
        return

    st.success(f"Matriz cargada: {len(df)} ingredientes.")

    etapa = st.selectbox("Etapa (Cerdos)", CERDOS_ETAPAS, key="cerdos_etapa")
    nutrientes = get_nutrient_list(df)

    preset = get_stage_preset("Cerdos", etapa)
    nutrientes_validos = [n for n in preset.keys() if n in nutrientes]

    st.write(f"Nutrientes preset compatibles: {len(nutrientes_validos)}")

    selected_nutrients = st.multiselect(
        "Nutrientes a usar",
        options=nutrientes,
        default=nutrientes_validos[: min(14, len(nutrientes_validos))],
        key="cerdos_nutrients",
    )

    req = {}
    for nut in selected_nutrients:
        p = preset.get(nut, {})
        req[nut] = {
            "min": float(p.get("min", 0) or 0),
            "max": float(p.get("max", 0) or 0),
        }

    if st.button("Formular dieta (Cerdos)", key="btn_solve_cerdos"):
        adapter = OptimizationAdapter()
        result = adapter.solve(
            ingredients_df=df,
            nutrient_list=selected_nutrients,
            requirements=req,
            limits={"min": {}, "max": {}},
            selected_species="Cerdos",
            selected_stage=etapa,
            ratios=[],
        )
        st.session_state["last_result_cerdos"] = result

    result = st.session_state.get("last_result_cerdos")
    if result:
        if result.get("success"):
            st.success("Formulación exitosa.")
            st.dataframe(
                pd.DataFrame(
                    list(result.get("diet", {}).items()),
                    columns=["Ingrediente", "Inclusión (%)"],
                ),
                use_container_width=True,
            )
            st.metric("Costo total (base 100 kg)", f"${result.get('cost', 0):.2f}")
        else:
            st.error(result.get("message", "No se pudo formular."))
            diag = result.get("infeasibility_diagnostics", [])
            if diag:
                st.write("Diagnóstico preliminar:")
                st.dataframe(pd.DataFrame(diag), use_container_width=True)
