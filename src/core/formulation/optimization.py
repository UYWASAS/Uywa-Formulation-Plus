import pulp
import pandas as pd


class DietFormulator:
    RATIO_DENOMINATOR_EPSILON = 1e-4

    def __init__(
        self,
        ingredients_df,
        nutrient_list,
        requirements,
        limits=None,
        selected_species=None,
        selected_stage=None,
        ratios=None,
    ):
        self.nutrient_list = nutrient_list or []
        self.requirements = requirements or {}
        self.ingredients_df = ingredients_df.copy()
        self.selected_species = selected_species
        self.selected_stage = selected_stage

        self.limits = limits if limits else {}
        self.limits.setdefault("min", {})
        self.limits.setdefault("max", {})

        self.ratios = ratios or []

    @staticmethod
    def _normalize_bound(value):
        try:
            bound = float(value)
        except Exception:
            return 0.0
        return bound if bound > 0 else 0.0

    @staticmethod
    def _error_result(message, infeasibility_diagnostics=None):
        return {
            "success": False,
            "message": message,
            "diet": {},
            "cost": 0,
            "nutritional_values": {},
            "compliance_data": [],
            "shadow_prices": {},
            "constraint_diagnostics": {},
            "infeasibility_diagnostics": infeasibility_diagnostics or [],
        }

    def _get_min_max_bounds(self, ingredient_name):
        """
        min/max ingresan en % (0..100). Se convierten a fracción (0..1).
        Reglas:
        - min por defecto = 0
        - max por defecto = 100
        - max=0 explícito se interpreta como 100 (no restringido), para evitar bloqueos por UI vacía.
        - clamp y consistencia min<=max
        """
        min_raw = self._normalize_bound(self.limits.get("min", {}).get(ingredient_name, 0))
        max_raw = self.limits.get("max", {}).get(ingredient_name, 100)

        # max robusto
        try:
            max_raw = float(max_raw)
        except Exception:
            max_raw = 100.0

        if max_raw <= 0:
            max_raw = 100.0  # no restringido

        # clamp 0..100
        min_raw = max(0.0, min(min_raw, 100.0))
        max_raw = max(0.0, min(max_raw, 100.0))

        # consistencia
        if min_raw > max_raw:
            min_raw = max_raw

        return min_raw / 100.0, max_raw / 100.0

    def _validate_limit_consistency(self):
        if self.ingredients_df is None or self.ingredients_df.empty or "Ingrediente" not in self.ingredients_df.columns:
            return None

        total_min = 0.0
        for i in self.ingredients_df.index:
            ing_name = str(self.ingredients_df.loc[i, "Ingrediente"])
            min_inc, max_inc = self._get_min_max_bounds(ing_name)
            if min_inc - max_inc > 1e-12:
                return f"Límite inválido: mínimo > máximo para ingrediente '{ing_name}'."
            total_min += min_inc

        if total_min > 1.0 + 1e-9:
            return f"Suma de mínimos por ingrediente excede 100% ({total_min*100:.4f}%)."

        return None

    def _calculate_theoretical_nutrient_bounds(self):
        diagnostics = []

        if self.ingredients_df is None or self.ingredients_df.empty:
            return diagnostics

        if "Ingrediente" not in self.ingredients_df.columns:
            return diagnostics

        for nutrient in self.nutrient_list:
            if nutrient not in self.ingredients_df.columns:
                continue

            req = self.requirements.get(nutrient, {})
            req_min = self._normalize_bound(req.get("min", 0))
            req_max = self._normalize_bound(req.get("max", 0))

            if req_min <= 0 and req_max <= 0:
                continue

            rows = []
            total_min_fixed = 0.0

            for i in self.ingredients_df.index:
                ing_name = str(self.ingredients_df.loc[i, "Ingrediente"])
                min_inc, max_inc = self._get_min_max_bounds(ing_name)

                try:
                    nutrient_value = float(self.ingredients_df.loc[i, nutrient])
                except Exception:
                    nutrient_value = 0.0

                if pd.isna(nutrient_value):
                    nutrient_value = 0.0

                rows.append(
                    {
                        "ingredient": ing_name,
                        "min_inc": min_inc,
                        "max_inc": max_inc,
                        "nutrient_value": nutrient_value,
                    }
                )

                total_min_fixed += min_inc

            if total_min_fixed > 1.0 + 1e-9:
                diagnostics.append(
                    {
                        "nutriente": nutrient,
                        "estado": "Posible inviabilidad por límites",
                        "requerido_min": req_min,
                        "requerido_max": req_max,
                        "max_teorico": None,
                        "min_teorico": None,
                        "detalle": f"La suma de mínimos de inclusión excede 100% ({total_min_fixed*100:.4f}%).",
                        "ingredientes_mayor_aporte": [],
                    }
                )
                continue

            remaining_after_min = max(0.0, 1.0 - total_min_fixed)

            max_theoretical = sum(row["min_inc"] * row["nutrient_value"] for row in rows)

            max_extra_capacity = []
            for row in rows:
                extra_capacity = max(0.0, row["max_inc"] - row["min_inc"])
                max_extra_capacity.append({**row, "extra_capacity": extra_capacity})

            max_extra_capacity = sorted(
                max_extra_capacity, key=lambda x: x["nutrient_value"], reverse=True
            )

            remaining = remaining_after_min
            for row in max_extra_capacity:
                if remaining <= 1e-12:
                    break
                add = min(row["extra_capacity"], remaining)
                max_theoretical += add * row["nutrient_value"]
                remaining -= add

            min_theoretical = sum(row["min_inc"] * row["nutrient_value"] for row in rows)

            min_extra_capacity = sorted(max_extra_capacity, key=lambda x: x["nutrient_value"])
            remaining = remaining_after_min
            for row in min_extra_capacity:
                if remaining <= 1e-12:
                    break
                add = min(row["extra_capacity"], remaining)
                min_theoretical += add * row["nutrient_value"]
                remaining -= add

            status = "OK"
            issue = ""

            if req_min > 0 and max_theoretical + 1e-9 < req_min:
                status = "Posible inviabilidad por mínimo"
                issue = (
                    f"El mínimo requerido para {nutrient} es {req_min:.4f}, "
                    f"pero el máximo teórico alcanzable con los límites actuales es "
                    f"{max_theoretical:.4f}."
                )

            elif req_max > 0 and min_theoretical - 1e-9 > req_max:
                status = "Posible inviabilidad por máximo"
                issue = (
                    f"El máximo permitido para {nutrient} es {req_max:.4f}, "
                    f"pero el mínimo teórico alcanzable con los límites actuales es "
                    f"{min_theoretical:.4f}."
                )

            if status != "OK":
                top_sources = sorted(rows, key=lambda x: x["nutrient_value"], reverse=True)[:3]
                diagnostics.append(
                    {
                        "nutriente": nutrient,
                        "estado": status,
                        "requerido_min": req_min,
                        "requerido_max": req_max,
                        "max_teorico": round(max_theoretical, 6),
                        "min_teorico": round(min_theoretical, 6),
                        "detalle": issue,
                        "ingredientes_mayor_aporte": [
                            {
                                "ingrediente": row["ingredient"],
                                "valor_nutriente": row["nutrient_value"],
                                "max_inclusion_%": round(row["max_inc"] * 100, 4),
                            }
                            for row in top_sources
                        ],
                    }
                )

        return diagnostics

    def check_feasibility(self):
        return self._calculate_theoretical_nutrient_bounds()

    def run(self):
        try:
            if self.ingredients_df is None or self.ingredients_df.empty:
                return self._error_result("No hay ingredientes disponibles para formular.")

            if "Ingrediente" not in self.ingredients_df.columns:
                return self._error_result("La matriz no contiene la columna 'Ingrediente'.")

            if "precio" not in self.ingredients_df.columns:
                return self._error_result("La matriz no contiene la columna 'precio'.")

            self.ingredients_df["precio"] = pd.to_numeric(
                self.ingredients_df["precio"], errors="coerce"
            ).fillna(0)

            for nutrient in self.nutrient_list:
                if nutrient in self.ingredients_df.columns:
                    self.ingredients_df[nutrient] = pd.to_numeric(
                        self.ingredients_df[nutrient], errors="coerce"
                    ).fillna(0)

            # validación temprana de límites
            limit_error = self._validate_limit_consistency()
            if limit_error:
                return self._error_result(limit_error)

            preliminary_infeasibility = self._calculate_theoretical_nutrient_bounds()

            prob = pulp.LpProblem("Diet_Formulation", pulp.LpMinimize)

            ingredient_vars = pulp.LpVariable.dicts(
                "Ing", self.ingredients_df.index, lowBound=0, upBound=1, cat="Continuous"
            )

            prob += pulp.lpSum(
                [self.ingredients_df.loc[i, "precio"] * ingredient_vars[i] for i in self.ingredients_df.index]
            ), "Total_Cost"

            prob += pulp.lpSum([ingredient_vars[i] for i in self.ingredients_df.index]) == 1, "Total_Proportion"

            for i in self.ingredients_df.index:
                ing_name = str(self.ingredients_df.loc[i, "Ingrediente"])
                min_inc, max_inc = self._get_min_max_bounds(ing_name)
                prob += ingredient_vars[i] >= min_inc, f"MinInc_{ing_name}"
                prob += ingredient_vars[i] <= max_inc, f"MaxInc_{ing_name}"

            for nutrient in self.nutrient_list:
                if nutrient not in self.ingredients_df.columns:
                    continue

                req = self.requirements.get(nutrient, {})
                min_val = self._normalize_bound(req.get("min", 0))
                max_val = self._normalize_bound(req.get("max", 0))

                expr = pulp.lpSum(
                    [self.ingredients_df.loc[i, nutrient] * ingredient_vars[i] for i in self.ingredients_df.index]
                )

                if min_val > 0:
                    prob += expr >= min_val, f"Min_{nutrient}"
                if max_val > 0:
                    prob += expr <= max_val, f"Max_{nutrient}"

            for idx, ratio in enumerate(self.ratios):
                num = ratio.get("numerador")
                den = ratio.get("denominador")
                op = ratio.get("operador")

                try:
                    val = float(ratio.get("valor"))
                except Exception:
                    return self._error_result(
                        f"Ratio inválido en posición {idx + 1}: valor no numérico.",
                        infeasibility_diagnostics=preliminary_infeasibility,
                    )

                if val <= 0:
                    return self._error_result(
                        f"Ratio inválido en posición {idx + 1}: valor menor o igual a cero.",
                        infeasibility_diagnostics=preliminary_infeasibility,
                    )

                if op not in {">=", "<=", "="}:
                    return self._error_result(
                        f"Ratio inválido en posición {idx + 1}: operador '{op}' no soportado.",
                        infeasibility_diagnostics=preliminary_infeasibility,
                    )

                if num == den:
                    return self._error_result(
                        f"Ratio inválido en posición {idx + 1}: numerador y denominador no pueden ser iguales.",
                        infeasibility_diagnostics=preliminary_infeasibility,
                    )

                if num not in self.nutrient_list or den not in self.nutrient_list:
                    return self._error_result(
                        f"Ratio inválido en posición {idx + 1}: nutrientes fuera de la selección.",
                        infeasibility_diagnostics=preliminary_infeasibility,
                    )

                if num not in self.ingredients_df.columns or den not in self.ingredients_df.columns:
                    return self._error_result(
                        f"Ratio inválido en posición {idx + 1}: nutrientes no disponibles en la matriz.",
                        infeasibility_diagnostics=preliminary_infeasibility,
                    )

                expr_num = pulp.lpSum(
                    [self.ingredients_df.loc[i, num] * ingredient_vars[i] for i in self.ingredients_df.index]
                )
                expr_den = pulp.lpSum(
                    [self.ingredients_df.loc[i, den] * ingredient_vars[i] for i in self.ingredients_df.index]
                )

                prob += expr_den >= self.RATIO_DENOMINATOR_EPSILON, f"RatioDenPos_{den}_{idx}"

                lhs = expr_num - val * expr_den
                op_key = {"<=": "LE", ">=": "GE", "=": "EQ"}[op]
                cname = f"Ratio_{num}_{op_key}_{den}_{idx}"

                if op == ">=":
                    prob += lhs >= 0, cname
                elif op == "<=":
                    prob += lhs <= 0, cname
                elif op == "=":
                    prob += lhs == 0, cname

            solver = pulp.PULP_CBC_CMD(msg=False)
            prob.solve(solver)

            diet = {}
            total_cost = 0
            nutritional_values = {}
            compliance_data = []
            shadow_prices = {}
            constraint_diagnostics = {}

            if pulp.LpStatus[prob.status] != "Optimal":
                return self._error_result(
                    f"Solver status: {pulp.LpStatus[prob.status]}",
                    infeasibility_diagnostics=preliminary_infeasibility,
                )

            for i in self.ingredients_df.index:
                amount = ingredient_vars[i].varValue * 100 if ingredient_vars[i].varValue is not None else 0
                if amount > 1e-6:
                    ingredient_name = self.ingredients_df.loc[i, "Ingrediente"]
                    diet[ingredient_name] = round(amount, 4)
                    total_cost += self.ingredients_df.loc[i, "precio"] * amount

            total_cost = round(total_cost, 2)

            for nutrient in self.nutrient_list:
                valor_nut = 0
                if nutrient in self.ingredients_df.columns:
                    for i in self.ingredients_df.index:
                        var_value = ingredient_vars[i].varValue or 0
                        amount = var_value * 100
                        nut_val = self.ingredients_df.loc[i, nutrient]
                        try:
                            nut_val = float(nut_val)
                        except Exception:
                            nut_val = 0
                        if pd.isna(nut_val):
                            nut_val = 0
                        valor_nut += nut_val * (amount / 100)
                nutritional_values[nutrient] = round(valor_nut, 4)

            for nutrient in self.nutrient_list:
                req = self.requirements.get(nutrient, {})
                req_min = self._normalize_bound(req.get("min", 0))
                req_max = self._normalize_bound(req.get("max", 0))
                obtenido = nutritional_values.get(nutrient, 0)

                if req_min or req_max:
                    if req_min and obtenido < req_min:
                        estado = "Deficiente"
                    elif req_max and obtenido > req_max:
                        estado = "Exceso"
                    else:
                        estado = "Cumple"
                else:
                    estado = "Sin restricción"

                compliance_data.append(
                    {
                        "Nutriente": nutrient,
                        "Mínimo": req_min,
                        "Máximo": req_max,
                        "Obtenido": obtenido,
                        "Estado": estado,
                    }
                )

            for constraint_name, constraint in prob.constraints.items():
                try:
                    shadow_value = constraint.pi
                except AttributeError:
                    shadow_value = None

                try:
                    slack_value = constraint.slack
                except AttributeError:
                    slack_value = None

                constraint_type = "Otro"
                related_item = constraint_name

                if constraint_name.startswith("Min_"):
                    constraint_type = "Mínimo nutricional"
                    related_item = constraint_name[4:]
                    shadow_prices[related_item] = shadow_value
                elif constraint_name.startswith("Max_"):
                    constraint_type = "Máximo nutricional"
                    related_item = constraint_name[4:]
                elif constraint_name.startswith("MinInc_"):
                    constraint_type = "Mínimo inclusión"
                    related_item = constraint_name.replace("MinInc_", "")
                elif constraint_name.startswith("MaxInc_"):
                    constraint_type = "Máximo inclusión"
                    related_item = constraint_name.replace("MaxInc_", "")
                elif constraint_name.startswith("RatioDenPos_"):
                    constraint_type = "Denominador ratio"
                    related_item = constraint_name
                elif constraint_name.startswith("Ratio_"):
                    constraint_type = "Ratio nutricional"
                    related_item = constraint_name
                elif constraint_name == "Total_Proportion":
                    constraint_type = "Suma fórmula"
                    related_item = "Total dieta"

                constraint_diagnostics[constraint_name] = {
                    "tipo": constraint_type,
                    "item": related_item,
                    "shadow_price": shadow_value,
                    "slack": slack_value,
                    "activa": abs(slack_value) < 1e-7 if slack_value is not None else None,
                }

            return {
                "success": True,
                "diet": diet,
                "cost": total_cost,
                "nutritional_values": nutritional_values,
                "compliance_data": compliance_data,
                "shadow_prices": shadow_prices,
                "constraint_diagnostics": constraint_diagnostics,
                "infeasibility_diagnostics": [],
            }

        except Exception as e:
            return self._error_result(f"Error interno del motor: {str(e)}")

    def solve(self):
        return self.run()
