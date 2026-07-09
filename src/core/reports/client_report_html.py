from datetime import datetime
import base64


def build_client_report_html(scenario: dict) -> str:
    """
    Genera HTML amigable para cliente final.
    Solo información relevante, profesional y auditible.
    """

    spec = scenario.get("spec_version", "1.0.0")
    scenario_id = scenario.get("scenario_id", "N/A")
    scenario_name = scenario.get("scenario_name", "N/A")
    created_at = scenario.get("created_at", "N/A")
    species = scenario.get("species", "N/A")
    stage = scenario.get("stage", "N/A")

    owner = scenario.get("owner", {})
    user = owner.get("user", "N/A")

    provenance = scenario.get("provenance", {})
    app_version = provenance.get("app_version", "N/A")
    currency = provenance.get("currency", "USD")
    basis = provenance.get("basis", "100kg")

    inputs = scenario.get("inputs", {})
    selected_ingredients = inputs.get("selected_ingredients", [])
    limits = inputs.get("limits", {})
    requirements = inputs.get("requirements", {})
    ratios = inputs.get("ratios", [])

    outputs = scenario.get("outputs", {})
    success = outputs.get("success", False)
    diet = outputs.get("diet", {})
    cost_100kg = outputs.get("cost", 0)
    nutritional_values = outputs.get("nutritional_values", {})
    compliance_data = outputs.get("compliance_data", [])

    analytics = scenario.get("analytics", {})
    kpis = analytics.get("kpis", {})

    cost_kg = cost_100kg / 100 if cost_100kg else 0
    cost_ton = cost_kg * 1000

    # Compilar dieta ordenada
    diet_sorted = sorted(diet.items(), key=lambda x: x[1], reverse=True)

    # HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Informe Formulación - {scenario_name}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f5f5f5;
                color: #333;
                line-height: 1.6;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
                background: #fff;
                padding: 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            header {{
                border-bottom: 3px solid #2176ff;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            header h1 {{
                color: #2C3E50;
                font-size: 28px;
                margin-bottom: 5px;
            }}
            header .meta {{
                font-size: 12px;
                color: #666;
                margin-top: 10px;
            }}
            .executive-summary {{
                background: #f0f7ff;
                border-left: 4px solid #2176ff;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 4px;
            }}
            .executive-summary h2 {{
                color: #2C3E50;
                font-size: 18px;
                margin-bottom: 15px;
            }}
            .kpi-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }}
            .kpi-card {{
                background: #fff;
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 4px;
                text-align: center;
            }}
            .kpi-card .label {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
                margin-bottom: 5px;
            }}
            .kpi-card .value {{
                font-size: 24px;
                font-weight: bold;
                color: #2176ff;
            }}
            section {{
                margin-bottom: 40px;
            }}
            section h2 {{
                color: #2C3E50;
                font-size: 20px;
                border-bottom: 2px solid #e0e0e0;
                padding-bottom: 10px;
                margin-bottom: 15px;
            }}
            section h3 {{
                color: #555;
                font-size: 14px;
                margin-top: 15px;
                margin-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            table thead {{
                background-color: #2C3E50;
                color: #fff;
            }}
            table th {{
                padding: 12px;
                text-align: left;
                font-weight: 600;
                font-size: 12px;
            }}
            table td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e0e0e0;
            }}
            table tbody tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            table tbody tr:hover {{
                background-color: #f0f0f0;
            }}
            .status-cumple {{
                color: #2ca25f;
                font-weight: bold;
            }}
            .status-deficiente {{
                color: #d9534f;
                font-weight: bold;
            }}
            .status-exceso {{
                color: #f0ad4e;
                font-weight: bold;
            }}
            .diagnostic-box {{
                background: #fff8f0;
                border-left: 4px solid #f0ad4e;
                padding: 15px;
                margin-bottom: 15px;
                border-radius: 4px;
            }}
            .diagnostic-box.success {{
                background: #f0f8f5;
                border-left-color: #2ca25f;
            }}
            .diagnostic-box.danger {{
                background: #fdf5f5;
                border-left-color: #d9534f;
            }}
            .footnote {{
                font-size: 11px;
                color: #999;
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
            }}
            .footer {{
                text-align: center;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 11px;
                color: #999;
            }}
            .ingredient-bar {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .ingredient-name {{
                flex: 0 0 150px;
                font-weight: 500;
            }}
            .ingredient-bar-viz {{
                flex: 1;
                height: 20px;
                background-color: #e8eef5;
                border-radius: 3px;
                overflow: hidden;
            }}
            .ingredient-bar-fill {{
                height: 100%;
                background: linear-gradient(90deg, #2176ff, #1254d1);
                display: flex;
                align-items: center;
                justify-content: flex-end;
                padding-right: 5px;
                color: white;
                font-size: 11px;
                font-weight: bold;
            }}
            .ingredient-pct {{
                flex: 0 0 60px;
                text-align: right;
                font-weight: 500;
                color: #2C3E50;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- ENCABEZADO -->
            <header>
                <h1>{scenario_name}</h1>
                <div class="meta">
                    <strong>Especie:</strong> {species} | <strong>Etapa:</strong> {stage}<br>
                    <strong>Fecha:</strong> {created_at} | <strong>Usuario:</strong> {user} | <strong>ID:</strong> {scenario_id}
                </div>
            </header>

            <!-- RESUMEN EJECUTIVO -->
            <div class="executive-summary">
                <h2>Resumen Ejecutivo</h2>
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="label">Costo / 100 kg</div>
                        <div class="value">${cost_100kg:.2f}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">Costo / kg</div>
                        <div class="value">${cost_kg:.2f}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">Costo / ton</div>
                        <div class="value">${cost_ton:,.2f}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">Ingredientes activos</div>
                        <div class="value">{len(diet)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">Cumplimiento nutricional</div>
                        <div class="value">{kpis.get("compliance_pct", 0):.1f}%</div>
                    </div>
                </div>
            </div>

            <!-- COMPOSICIÓN ÓPTIMA -->
            <section>
                <h2>Composición Óptima de la Dieta</h2>
                <p><em>Porcentaje de inclusión de cada ingrediente en la formulación final.</em></p>
    """

    for ing, pct in diet_sorted:
        pct_safe = float(pct) if pct else 0
        html += f"""
                <div class="ingredient-bar">
                    <div class="ingredient-name">{ing}</div>
                    <div class="ingredient-bar-viz">
                        <div class="ingredient-bar-fill" style="width: {pct_safe}%">
                            {pct_safe:.2f}%
                        </div>
                    </div>
                    <div class="ingredient-pct">{pct_safe:.3f}%</div>
                </div>
        """

    html += """
            </section>

            <!-- CUMPLIMIENTO NUTRICIONAL -->
            <section>
                <h2>Cumplimiento Nutricional</h2>
                <p><em>Estado de cada nutriente frente a los requerimientos definidos.</em></p>
                <table>
                    <thead>
                        <tr>
                            <th>Nutriente</th>
                            <th>Mínimo</th>
                            <th>Máximo</th>
                            <th>Obtenido</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for row in compliance_data:
        nut = row.get("Nutriente", "N/A")
        min_v = row.get("Mínimo", "—")
        max_v = row.get("Máximo", "—")
        obt = row.get("Obtenido", "—")
        estado = row.get("Estado", "N/A")

        if isinstance(min_v, (int, float)):
            min_v = f"{min_v:.3f}"
        if isinstance(max_v, (int, float)):
            max_v = f"{max_v:.3f}"
        if isinstance(obt, (int, float)):
            obt = f"{obt:.3f}"

        estado_class = "status-cumple" if "cumple" in str(estado).lower() else (
            "status-deficiente" if "deficiente" in str(estado).lower() else (
                "status-exceso" if "exceso" in str(estado).lower() else ""
            )
        )

        html += f"""
                        <tr>
                            <td><strong>{nut}</strong></td>
                            <td>{min_v}</td>
                            <td>{max_v}</td>
                            <td>{obt}</td>
                            <td class="{estado_class}">{estado}</td>
                        </tr>
        """

    html += """
                    </tbody>
                </table>
            </section>

            <!-- DIAGNÓSTICO ECONÓMICO -->
            <section>
                <h2>Diagnóstico Económico</h2>
                <p><em>Análisis de costos e impacto de ingredientes y nutrientes.</em></p>
    """

    analytics = scenario.get("analytics", {})
    economic_drivers = analytics.get("economic_drivers", [])

    if economic_drivers and len(economic_drivers) > 0:
        top_driver = economic_drivers[0]
        html += f"""
                <div class="diagnostic-box success">
                    <strong>Nutriente principal limitante:</strong> {top_driver.get('nutriente', 'N/A')}<br>
                    Costo marginal: ${top_driver.get('costo_marginal_ton', 0):.2f}/ton<br>
                    Impacto relativo: {top_driver.get('impacto_pct', 0):.3f}%
                </div>
        """

    html += """
            </section>

            <!-- SUPUESTOS Y TRAZABILIDAD -->
            <section>
                <h2>Supuestos y Trazabilidad</h2>
                <table>
                    <tr>
                        <td><strong>Versión de aplicación:</strong></td>
                        <td>{app_version}</td>
                    </tr>
                    <tr>
                        <td><strong>Moneda:</strong></td>
                        <td>{currency}</td>
                    </tr>
                    <tr>
                        <td><strong>Base de cálculo:</strong></td>
                        <td>{basis}</td>
                    </tr>
                    <tr>
                        <td><strong>Especificación de escenario:</strong></td>
                        <td>UYWA Scenario Spec v{spec}</td>
                    </tr>
                    <tr>
                        <td><strong>Fecha generación:</strong></td>
                        <td>{created_at}</td>
                    </tr>
                </table>
            </section>

            <!-- FOOTER -->
            <div class="footer">
                <p>Informe generado por UYWA Nutrition | Nutrición de Precisión Basada en Evidencia</p>
                <p>© 2026 UYWA. Todos los derechos reservados.</p>
            </div>
        </div>
    </body>
    </html>
    """.format(
        app_version=app_version,
        currency=currency,
        basis=basis,
        spec=spec,
        created_at=created_at,
    )

    return html
