import streamlit as st


UYWA_COLORS = {
    "bg_start": "#ffffff",
    "bg_end": "#eef4fc",
    "sidebar_bg": "#2C3E50",
    "primary": "#2176ff",
    "primary_hover": "#1254d1",
    "success": "#2ca25f",
    "warning": "#f0ad4e",
    "danger": "#d9534f",
    "text_dark": "#2C3E50",
    "text_body": "#333333",
    "border": "#d9e6f7",
}


def apply_theme():
    """Aplica tema visual global UYWA Premium (sin alterar lógica de cálculo)."""
    st.markdown(
        f"""
        <style>
        html, body, .stApp, .block-container {{
            background: linear-gradient(120deg, {UYWA_COLORS["bg_start"]} 0%, {UYWA_COLORS["bg_end"]} 100%) !important;
        }}

        .block-container {{
            padding: 1.2rem 2rem;
        }}

        section[data-testid="stSidebar"] {{
            background-color: {UYWA_COLORS["sidebar_bg"]} !important;
            color: #fff !important;
            width: 18.5rem !important;
            min-width: 18.5rem !important;
            max-width: 18.5rem !important;
        }}

        section[data-testid="stSidebar"] * {{
            color: #fff !important;
        }}

        .stButton > button {{
            background-color: {UYWA_COLORS["primary"]};
            color: #fff !important;
            border-radius: 10px;
            border: none;
            padding: 0.55rem 1rem !important;
            font-weight: 600;
        }}

        .stButton > button:hover {{
            background-color: {UYWA_COLORS["primary_hover"]};
            color: #fff !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.18) !important;
        }}

        .stNumberInput, .stSelectbox, .stTextInput {{
            background-color: #eef4fc !important;
            border-radius: 8px;
            border: 1px solid #d4e4fc !important;
        }}

        footer {{
            visibility: hidden !important;
        }}

        .uywa-card {{
            background: #ffffff;
            border-radius: 12px;
            padding: 18px 20px;
            margin: 12px 0;
            border: 1px solid {UYWA_COLORS["border"]};
            box-shadow: 0 3px 10px rgba(44, 62, 80, 0.08);
        }}

        .uywa-card-info {{ border-left: 6px solid {UYWA_COLORS["primary"]}; }}
        .uywa-card-success {{ border-left: 6px solid {UYWA_COLORS["success"]}; }}
        .uywa-card-warning {{
            border-left: 6px solid {UYWA_COLORS["warning"]};
            background: #fffaf0;
        }}
        .uywa-card-danger {{
            border-left: 6px solid {UYWA_COLORS["danger"]};
            background: #fff3f3;
        }}

        .uywa-card-title {{
            margin: 0 0 6px 0;
            color: {UYWA_COLORS["text_dark"]};
            font-size: 18px;
            font-weight: 700;
        }}

        .uywa-card-body {{
            margin: 0;
            color: {UYWA_COLORS["text_body"]};
            font-size: 14px;
            line-height: 1.45;
        }}

        .uywa-section-title {{
            color: {UYWA_COLORS["text_dark"]};
            font-weight: 800;
            margin-top: 1rem;
            margin-bottom: .2rem;
        }}

        .uywa-section-subtitle {{
            color: #627386;
            font-size: 14px;
            margin-bottom: 0.8rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_sidebar(user: dict | None = None):
    """Header lateral con branding y estado del plan."""
    with st.sidebar:
        st.image("assets/logo.png", use_container_width=True)
        st.markdown(
            """
            <div style="text-align:center;margin-bottom:20px;">
                <h1 style="font-family:Montserrat,sans-serif;margin:0;color:#fff;">UYWA Nutrition</h1>
                <p style="font-size:14px;margin:0;color:#fff;">Nutrición de Precisión Basada en Evidencia</p>
                <br>
                <hr style="border:1px solid #fff;">
                <p style="font-size:13px;color:#fff;margin:0;">📧 uywasas@gmail.com</p>
                <p style="font-size:11px;color:#fff;margin:0;">Derechos reservados © 2026</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if user:
            plan = user.get("plan", "Sin plan")
            expires = user.get("expires")
            st.success(f"Acceso {plan} activado")
            if expires:
                st.caption(f"Válido hasta: {expires}")
        else:
            st.warning("Por favor, inicia sesión.")
