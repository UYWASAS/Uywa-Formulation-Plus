import streamlit as st


class OptimizationAdapter:
    """
    Adaptador temporal para desacoplar la UI del solver legacy.
    Intenta importar DietFormulator desde distintos caminos.
    """

    def __init__(self):
        self._solver_cls = self._resolve_solver_class()

    def _resolve_solver_class(self):
        # 1) Ruta legacy (si existe optimization.py en raíz)
        try:
            from optimization import DietFormulator  # type: ignore
            return DietFormulator
        except Exception:
            pass

        # 2) Ruta modular sugerida (si luego mueves solver a src/core/formulation/)
        try:
            from src.core.formulation.optimization import DietFormulator  # type: ignore
            return DietFormulator
        except Exception:
            pass

        return None

    def solve(
        self,
        ingredients_df,
        nutrient_list,
        requirements,
        limits,
        selected_species,
        selected_stage,
        ratios,
    ):
        if self._solver_cls is None:
            return {
                "success": False,
                "message": (
                    "No se encontró DietFormulator. "
                    "Define el solver en 'optimization.py' (raíz) "
                    "o en 'src/core/formulation/optimization.py'."
                ),
                "diet": {},
                "cost": 0,
                "nutritional_values": {},
                "compliance_data": [],
                "constraint_diagnostics": {},
                "infeasibility_diagnostics": [],
            }

        try:
            formulator = self._solver_cls(ingredients_df)
            return formulator.formulate(
                nutrient_list=nutrient_list,
                requirements=requirements,
                limits=limits,
                selected_species=selected_species,
                selected_stage=selected_stage,
                ratios=ratios,
            )
        except Exception as e:
            st.exception(e)
            return {
                "success": False,
                "message": f"Error en optimización: {e}",
                "diet": {},
                "cost": 0,
                "nutritional_values": {},
                "compliance_data": [],
                "constraint_diagnostics": {},
                "infeasibility_diagnostics": [],
            }
