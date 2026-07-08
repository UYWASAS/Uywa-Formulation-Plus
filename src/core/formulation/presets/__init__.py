from requirements_presets import PRESETS as LEGACY_PRESETS


def get_all_presets():
    """
    Punto único de acceso para presets.
    En esta fase usa el archivo legacy completo para no romper nada.
    Luego migraremos especie por especie a módulos separados.
    """
    return LEGACY_PRESETS


def get_species_presets(species: str):
    return get_all_presets().get(species, {})


def get_stage_preset(species: str, stage: str):
    return get_species_presets(species).get(stage, {})
