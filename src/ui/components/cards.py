import streamlit as st


def render_card(title: str, body: str, variant: str = "info"):
    variant_class = {
        "info": "uywa-card-info",
        "success": "uywa-card-success",
        "warning": "uywa-card-warning",
        "danger": "uywa-card-danger",
    }.get(variant, "uywa-card-info")

    st.markdown(
        f"""
        <div class="uywa-card {variant_class}">
            <div class="uywa-card-title">{title}</div>
            <p class="uywa-card-body">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, caption: str = ""):
    st.markdown(
        f"""
        <div class="uywa-card uywa-card-info">
            <div class="uywa-card-title" style="font-size:14px;font-weight:600;">{label}</div>
            <div style="font-size:28px;font-weight:800;color:#2C3E50;">{value}</div>
            <div style="font-size:12px;color:#7a8694;">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
