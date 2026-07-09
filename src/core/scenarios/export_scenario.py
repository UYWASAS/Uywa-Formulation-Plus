import zipfile
from io import BytesIO
import json
from datetime import datetime


def export_scenario_zip(
    scenario_payload: dict,
    html_content: str,
    scenario_name: str = None,
) -> BytesIO:
    """
    Crea un ZIP descargable con:
    - scenario.json (payload técnico)
    - informe_cliente.html (visual para cliente)
    - README.txt (instrucciones)
    """

    if not scenario_name:
        scenario_name = scenario_payload.get("scenario_name", "escenario")

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) JSON técnico
        scenario_json = json.dumps(scenario_payload, ensure_ascii=False, indent=2)
        zf.writestr(
            "scenario.json",
            scenario_json,
        )

        # 2) HTML amigable
        zf.writestr(
            "informe_cliente.html",
            html_content,
        )

        # 3) README con instrucciones
        readme = f"""ESCENARIO TÉCNICO UYWA - {scenario_name}
===============================================

Contenido del archivo:
- scenario.json: Payload técnico (compatible para análisis avanzado y comparación)
- informe_cliente.html: Informe visual para cliente (abrir en navegador)
- README.txt: Este archivo

INSTRUCCIONES:
1. Abre 'informe_cliente.html' en tu navegador para ver el informe completo.
2. Carga 'scenario.json' en la funcionalidad de "Comparar dietas" para análisis avanzado.

ESPECIFICACIÓN:
- Versión: UYWA Scenario Spec v1.0.0
- Fecha: {datetime.utcnow().isoformat()}
- Usuario: {scenario_payload.get('owner', {}).get('user', 'N/A')}

Para más información, contacta a UYWA Nutrition.
"""
        zf.writestr("README.txt", readme)

    zip_buffer.seek(0)
    return zip_buffer
