from src.core.formulation.optimization import DietFormulator


class OptimizationAdapter:
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
        formulator = DietFormulator(
            ingredients_df=ingredients_df,
            nutrient_list=nutrient_list,
            requirements=requirements,
            limits=limits,
            selected_species=selected_species,
            selected_stage=selected_stage,
            ratios=ratios,
        )
        return formulator.solve()
