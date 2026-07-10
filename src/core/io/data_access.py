import io

import pandas as pd
import streamlit as st

from src.core.formulation.presets.data import PRESETS


NON_NUTRIENT_COLUMNS = {
    "ingrediente", "ingredient", "nombre", "name", "marca", "brand",
    "precio", "price", "costo", "cost", "unidad", "unit",
    "categoria", "category", "grupo", "group", "tipo", "type",
    "origen", "origin", "fuente", "source", "observacion",
    "observaciones", "nota", "notas", "codigo", "código", "id",
    "materia seca (%)",
}

MISSING_MARKERS = {"", ".", "-", "--", "nd", "n.d.", "na", "n/a", "s/d", "sd"}


def _normalize_column_name(value) -> str:
    return str(value).strip()


def _read_csv_robust(uploaded_file) -> pd.DataFrame:
    """Lee CSV conservando todas las columnas y probando separadores/codificaciones."""
    try:
        raw = uploaded_file.getvalue()
    except Exception:
        uploaded_file.seek(0)
        raw = uploaded_file.read()

    attempts = [
        {"sep": None, "engine": "python", "encoding": "utf-8-sig"},
        {"sep": None, "engine": "python", "encoding": "latin1"},
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": "\t", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
    ]

    candidates = []
    for kwargs in attempts:
        try:
            df = pd.read_csv(io.BytesIO(raw), **kwargs)
            if df is not None and not df.empty:
                candidates.append(df)
        except Exception:
            continue
    if not candidates:
        return pd.DataFrame()
    return max(candidates, key=lambda d: len(d.columns))


def load_ingredients(uploaded_file):
    """Carga CSV/XLS/XLSX sin filtrar columnas por especie ni por preset."""
    if uploaded_file is None:
        return pd.DataFrame()

    filename = str(getattr(uploaded_file, "name", "")).lower()
    try:
        uploaded_file.seek(0)
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        elif filename.endswith(".csv"):
            df = _read_csv_robust(uploaded_file)
        else:
            st.error("Formato no soportado. Usa .csv, .xls o .xlsx")
            return pd.DataFrame()
    except Exception as exc:
        st.error(f"Error al cargar ingredientes: {exc}")
        return pd.DataFrame()

    if df is None or df.empty:
        st.error("La matriz no contiene datos legibles.")
        return pd.DataFrame()

    df = df.copy()
    df.columns = [_normalize_column_name(c) for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="first")]
    return df


def _numeric_series(series: pd.Series) -> pd.Series:
    """Convierte columnas parcialmente numéricas, con coma decimal y porcentaje."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    s = series.astype(str).str.strip()
    lower = s.str.lower()
    s = s.mask(lower.isin(MISSING_MARKERS))
    s = s.str.replace("%", "", regex=False)
    s = s.str.replace(r"\s+", "", regex=True)
    both = s.str.contains(",", na=False) & s.str.contains(r"\.", na=False)
    s.loc[both] = s.loc[both].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    only_comma = s.str.contains(",", na=False) & ~s.str.contains(r"\.", na=False)
    s.loc[only_comma] = s.loc[only_comma].str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def get_nutrient_list(ingredients_df):
    """Devuelve todas las columnas nutricionales detectables de la matriz activa."""
    if ingredients_df is None or ingredients_df.empty:
        return []

    nutrients = []
    for col in ingredients_df.columns:
        name = _normalize_column_name(col)
        if not name or name.lower() in NON_NUTRIENT_COLUMNS:
            continue
        numeric = _numeric_series(ingredients_df[col])
        if numeric.notna().any():
            nutrients.append(name)
    return nutrients


def get_preset_requirements(especie, etapa):
    return PRESETS.get(especie, {}).get(etapa, {})
