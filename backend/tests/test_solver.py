from __future__ import annotations

import numpy as np
import pytest

from app.models.schemas import CalcRequest, MaterialsInput, OxideComposition, ProcessParams
from app.services.solver import MSG_NO_SO3, SolverError, example_materials, solve_blend


def _req(**overrides) -> CalcRequest:
    mats = example_materials()
    mats.update(overrides)
    return CalcRequest(materials=MaterialsInput.model_validate(mats), batch_mass=100)


def test_example_satisfies_hard_constraints():
    result = solve_blend(_req(), rng=np.random.default_rng(0), pollution=False)
    assert abs(result.masses.total - 100) < 1e-6
    assert abs(result.percents.total - 100) <= 1e-6
    assert result.percents.total <= 100.0001
    assert abs(result.masses.carbide_slag - 6) < 1e-6
    assert result.checks.al2o3_so3.passed
    assert result.checks.cao_ratio.passed
    assert result.checks.gangue_flyash.passed
    assert result.checks.total_mass.passed
    assert result.checks.carbide_slag.passed
    assert result.masses.coal_gangue >= -1e-9
    assert result.masses.fly_ash >= -1e-9
    assert result.masses.limestone >= -1e-9
    assert result.masses.gypsum >= -1e-9
    ratio = result.masses.fly_ash / result.masses.coal_gangue
    assert 1.96 - 1e-6 <= ratio <= 2.04 + 1e-6
    assert abs(ratio - 2.0) < 1e-4


def test_pollution_stays_in_band():
    ratios = []
    for seed in range(12):
        result = solve_blend(_req(), rng=np.random.default_rng(seed), pollution=True)
        ratio = result.masses.fly_ash / result.masses.coal_gangue
        ratios.append(ratio)
        assert 1.96 - 1e-5 <= ratio <= 2.04 + 1e-5
        assert result.checks.al2o3_so3.passed
        assert result.checks.cao_ratio.passed
        assert abs(result.masses.carbide_slag - 6) < 1e-6
        assert result.percents.total <= 100.0001
    assert max(ratios) - min(ratios) > 1e-6


def test_empty_oxide_treated_as_zero():
    mats = example_materials()
    mats["limestone"]["SO3"] = None  # type: ignore[assignment]
    req = CalcRequest(materials=MaterialsInput.model_validate(mats), batch_mass=100)
    assert req.materials.limestone.so3 == 0
    result = solve_blend(req, rng=np.random.default_rng(1), pollution=False)
    assert result.checks.al2o3_so3.passed


def test_row_sum_over_100_rejected():
    mats = example_materials()
    mats["coal_gangue"]["SiO2"] = 90
    mats["coal_gangue"]["Al2O3"] = 20
    with pytest.raises(ValueError):
        CalcRequest(materials=MaterialsInput.model_validate(mats), batch_mass=100)


def test_gypsum_without_so3_raises():
    mats = example_materials()
    for key in mats:
        mats[key]["SO3"] = 0
    req = CalcRequest(materials=MaterialsInput.model_validate(mats), batch_mass=100)
    with pytest.raises(SolverError) as exc:
        solve_blend(req, pollution=False)
    assert exc.value.code == "no_so3"
    assert MSG_NO_SO3 in exc.value.message


def test_batch_mass_scales():
    result = solve_blend(
        CalcRequest(materials=MaterialsInput.model_validate(example_materials()), batch_mass=250),
        rng=np.random.default_rng(2),
        pollution=False,
    )
    assert abs(result.masses.total - 250) < 1e-5
    assert abs(result.masses.carbide_slag - 15) < 1e-5
    assert abs(result.percents.carbide_slag - 6) < 1e-4


def test_custom_params():
    params = ProcessParams(al2o3_so3_target=4.0, cao_factor=1.03, carbide_slag_ratio=0.06)
    req = CalcRequest(
        materials=MaterialsInput.model_validate(example_materials()),
        batch_mass=100,
        params=params,
    )
    result = solve_blend(req, rng=np.random.default_rng(3), pollution=False)
    assert abs(result.checks.al2o3_so3.actual - 4.0) < 1e-4


def test_blank_composition_object():
    OxideComposition()
    blank = OxideComposition.model_validate({"SiO2": "", "Al2O3": None, "CaO": 1})
    assert blank.sio2 == 0
    assert blank.al2o3 == 0
    assert blank.cao == 1
