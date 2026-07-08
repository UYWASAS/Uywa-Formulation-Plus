import streamlit as st
import pandas as pd

from src.core.io.data_access import load_ingredients, get_nutrient_list
from src.core.formulation.presets import get_stage_preset
from src.adapters.optimization_adapter import OptimizationAdapter


RUMIANTES_ETAPAS = [
    "Ternera transición 80 kg - 800 g/d",
    "Ternera transición 80 kg - 950 g/d",
    "Ternera transición 80 kg - 1100 g/d",
    "Ternera transición 100 kg - 800 g/d",
    "Ternera transición 100 kg - 1000 g/d",
    "Ternera transición 100 kg - 1200 g/d",
    "Ternera transición 125 kg - 800 g/d",
    "Ternera transición 125 kg - 1000 g/d",
    "Ternera transición 125 kg - 1200 g/d",
    "Novilla recría 180 kg - 900 g/d",
    "Novilla recría 270 kg - 800 g/d",
    "Novilla recría 405 kg - 800 g/d",
    "Novilla gestación 600 kg - 800 g/d",
    "Novilla preparto 680 kg - 700 g/d",
    "Vaca producción 20 L - baja",
    "Vaca producción 30 L - media",
    "Vaca producción 40 L - alta",
    "Vaca producción 50 L - muy alta",
]


def render():
    st.title("Formulador · Rumiantes")
    st.caption("Módulo modular conectado al mismo motor de cálculo (DietFormulator).")

    up = st.file_uploader(
        "Matriz de ingredientes (.csv/.xlsx)",
        type=["csv", "xlsx"],
        key="rumiantes_matriz_upload",
    )

    df = load_ingredients(up)
    if df is None or df.empty:
        st.info("Carga una matriz para comenzar.")
        return

    if "Ingrediente" not in df.columns or "precio" not in df.columns:
        st.error("La matriz debe contener columnas 'Ingrediente' y 'precio'.")
        return

    st.success(f"Matriz cargada: {len(df)} ingredientes.")

    etapa = st.selectbox("Etapa (Rumiantes)", RUMIANTES_ETAPAS, key="rumiantes_etapa")
    nutrientes = get_nutrient_list(df)

    preset = get_stage_preset("Rumiantes", etapa)
    nutrientes_validos = [n for n in preset.keys() if n in nutrientes]

    st.write(f"Nutrientes preset compatibles: {len(nutrientes_validos)}")

    selected_nutrients = st.multiselect(
        "Nutrientes a usar",
        options=nutrientes,
        default=nutrientes_validos[: min(14, len(nutrientes_validos))],
        key="rumiantes_nutrients",
    )

    req = {}
    for nut in selected_nutrients:
        p = preset.get(nut, {})
        req[nut] = {
            "min": float(p.get("min", 0) or 0),
            "max": float(p.get("max", 0) or 0),
        }

    if st.button("Formular dieta (Rumiantes)", key="btn_solve_rumiantes"):
        adapter = OptimizationAdapter()
        result = adapter.solve(
            ingredients_df=df,
            nutrient_list=selected_nutrients,
            requirements=req,
            limits={"min": {}, "max": {}},
            selected_species="Rumiantes",
            selected_stage=etapa,
            ratios=[],
        )
        st.session_state["last_result_rumiantes"] = result

    result = st.session_state.get("last_result_rumiantes")
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
