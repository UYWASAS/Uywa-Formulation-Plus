from optimization import DietFormulator


class OptimizationAdapter:
    """
    Adapter para conservar 100% del comportamiento del solver legado
    mientras reorganizamos la app por módulos/páginas.
    """

    def __init__(self):
        self.engine_cls = DietFormulator

    def build_formulator(
        self,
        ingredients_df,
        nutrient_list,
        requirements,
        limits=None,
        selected_species=None,
        selected_stage=None,
        ratios=None,
    ):
        return self.engine_cls(
            ingredients_df=ingredients_df,
            nutrient_list=nutrient_list,
            requirements=requirements,
            limits=limits,
            selected_species=selected_species,
            selected_stage=selected_stage,
            ratios=ratios,
        )

    def solve(
        self,
        ingredients_df,
        nutrient_list,
        requirements,
        limits=None,
        selected_species=None,
        selected_stage=None,
        ratios=None,
    ):
        formulator = self.build_formulator(
            ingredients_df=ingredients_df,
            nutrient_list=nutrient_list,
            requirements=requirements,
            limits=limits,
            selected_species=selected_species,
            selected_stage=selected_stage,
            ratios=ratios,
        )
        return formulator.solve()

    def check_feasibility(
        self,
        ingredients_df,
        nutrient_list,
        requirements,
        limits=None,
        selected_species=None,
        selected_stage=None,
        ratios=None,
    ):
        formulator = self.build_formulator(
            ingredients_df=ingredients_df,
            nutrient_list=nutrient_list,
            requirements=requirements,
            limits=limits,
            selected_species=selected_species,
            selected_stage=selected_stage,
            ratios=ratios,
        )
        return formulator.check_feasibility()
