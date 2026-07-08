from src.core.formulation.presets.data import PRESETS


def get_all_presets():
    return PRESETS


def get_species_presets(species: str):
    return PRESETS.get(species, {})


def get_stage_preset(species: str, stage: str):
    return PRESETS.get(species, {}).get(stage, {})
