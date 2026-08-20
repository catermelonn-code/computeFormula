"""基于化验成分与工艺化学计量关系的多原料约束配料求解。

硬约束：
- x + y + z + w + V = T
- V = carbide_slag_ratio * T
- n(Al2O3) / n(SO3) = al2o3_so3_target
- n(CaO) / ((12/7) n(Al2O3) + 2 n(SiO2)) = cao_factor
- ratio_low <= y/x <= ratio_high
- x, y, z, w, V >= 0

优化目标：使 y/x 接近目标比，同时在允许带内注入小随机扰动，避免结果可被反推。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import linalg, optimize

from app.models.schemas import (
    BlendMasses,
    BlendPercents,
    CalcChecks,
    CalcRequest,
    CalcResult,
    CheckItem,
    OxideComposition,
    OxideMoles,
    OxideTotals,
    ProcessParams,
)

EQ_ATOL = 1e-7
MASS_ATOL = 1e-6
NONNEG_ATOL = 1e-8


class SolverError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


MSG_NO_FEASIBLE = "当前原料化验数据无法同时满足全部工艺约束，请检查原料成分或调整工艺参数。"
MSG_NO_SO3 = "当前原料无法提供满足硫配比要求的 SO₃，请检查脱硫石膏化验数据。"
MSG_RATIO = "当前化验数据下无法同时满足煤矸石:粉煤灰约1:2的工艺要求。"


@dataclass(frozen=True)
class _MaterialSet:
    names: tuple[str, ...]
    comps: tuple[OxideComposition, ...]

    @property
    def al2o3(self) -> np.ndarray:
        return np.array([c.al2o3 for c in self.comps], dtype=float)

    @property
    def sio2(self) -> np.ndarray:
        return np.array([c.sio2 for c in self.comps], dtype=float)

    @property
    def cao(self) -> np.ndarray:
        return np.array([c.cao for c in self.comps], dtype=float)

    @property
    def so3(self) -> np.ndarray:
        return np.array([c.so3 for c in self.comps], dtype=float)


def default_params() -> ProcessParams:
    return ProcessParams()


def example_materials() -> dict:
    return {
        "coal_gangue": {
            "SiO2": 42.71, "Al2O3": 30.01, "CaO": 0.59,
            "Fe2O3": 4.48, "MgO": 0.18, "SO3": 0.84,
        },
        "fly_ash": {
            "SiO2": 36.37, "Al2O3": 45.80, "CaO": 5.10,
            "Fe2O3": 4.19, "MgO": 0.32, "SO3": 0.93,
        },
        "limestone": {
            "SiO2": 3.21, "Al2O3": 0.77, "CaO": 52.34,
            "Fe2O3": 0.14, "MgO": 1.14, "SO3": 0,
        },
        "gypsum": {
            "SiO2": 2.15, "Al2O3": 0.73, "CaO": 38.09,
            "Fe2O3": 0.12, "MgO": 0.29, "SO3": 54.41,
        },
        "carbide_slag": {
            "SiO2": 3.85, "Al2O3": 1.34, "CaO": 64.05,
            "Fe2O3": 0.24, "MgO": 1.80, "SO3": 0,
        },
    }


def _materials_from_request(req: CalcRequest) -> _MaterialSet:
    m = req.materials
    return _MaterialSet(
        names=("煤矸石", "粉煤灰", "石灰石", "脱硫石膏", "电石渣"),
        comps=(m.coal_gangue, m.fly_ash, m.limestone, m.gypsum, m.carbide_slag),
    )


def _sulfur_coeff(comp: OxideComposition, params: ProcessParams) -> float:
    """4 * n(SO3) - n(Al2O3) 对单位质量的线性系数（含量为质量百分比）。"""
    n_so3 = (comp.so3 / 100.0) / params.mw_so3
    n_al = (comp.al2o3 / 100.0) / params.mw_al2o3
    return params.al2o3_so3_target * n_so3 - n_al


def _calcium_coeff(comp: OxideComposition, params: ProcessParams) -> float:
    """n(CaO) - k * ((12/7) n(Al2O3) + 2 n(SiO2)) 对单位质量的线性系数。"""
    n_cao = (comp.cao / 100.0) / params.mw_cao
    n_al = (comp.al2o3 / 100.0) / params.mw_al2o3
    n_si = (comp.sio2 / 100.0) / params.mw_sio2
    theory = params.al_coeff * n_al + params.si_coeff * n_si
    return n_cao - params.cao_factor * theory


def _sample_polluted_ratio(params: ProcessParams, rng: np.random.Generator) -> float:
    """在 煤矸石×[1-δ,1+δ]、粉煤灰×[target×(1-δ), target×(1+δ)] 内采样，且 y/x 落在允许带。"""
    x_lo, x_hi = 1.0 - params.ratio_tolerance, 1.0 + params.ratio_tolerance
    y_lo, y_hi = params.ratio_low, params.ratio_high
    for _ in range(32):
        kx = float(rng.uniform(x_lo, x_hi))
        intersect_lo = max(y_lo, y_lo * kx)
        intersect_hi = min(y_hi, y_hi * kx)
        if intersect_hi < intersect_lo:
            continue
        ky = float(rng.uniform(intersect_lo, intersect_hi))
        ratio = ky / kx
        if params.ratio_low - 1e-12 <= ratio <= params.ratio_high + 1e-12:
            return ratio
    return float(np.clip(
        params.gangue_flyash_target,
        params.ratio_low,
        params.ratio_high,
    ))


def _solve_linear(a_coeff: np.ndarray, b_coeff: np.ndarray, v: float, remain: float, ratio: float) -> np.ndarray | None:
    """未知数 [x, y, z, w]，等式：总质量、y=ratio*x、硫约束、钙约束。"""
    matrix = np.array(
        [
            [1.0, 1.0, 1.0, 1.0],
            [-ratio, 1.0, 0.0, 0.0],
            [a_coeff[0], a_coeff[1], a_coeff[2], a_coeff[3]],
            [b_coeff[0], b_coeff[1], b_coeff[2], b_coeff[3]],
        ],
        dtype=float,
    )
    rhs = np.array(
        [
            remain,
            0.0,
            -a_coeff[4] * v,
            -b_coeff[4] * v,
        ],
        dtype=float,
    )
    try:
        cond = np.linalg.cond(matrix)
        if not np.isfinite(cond) or cond > 1e12:
            return None
        sol = linalg.solve(matrix, rhs, assume_a="gen")
    except linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(sol)):
        return None
    if np.any(sol < -NONNEG_ATOL):
        return None
    return np.maximum(sol, 0.0)


def _pack(xyzw: np.ndarray, v: float) -> np.ndarray:
    return np.array([xyzw[0], xyzw[1], xyzw[2], xyzw[3], v], dtype=float)


def _solve_slsqp(
    a_coeff: np.ndarray,
    b_coeff: np.ndarray,
    v: float,
    remain: float,
    params: ProcessParams,
    ratio_target: float,
    x0: np.ndarray | None,
) -> np.ndarray | None:
    """4 变量 [x,y,z,w]，硫/钙/总质量为等式，y/x 落在允许带，目标贴近受污染比例。"""

    def objective(var: np.ndarray) -> float:
        x, y = var[0], var[1]
        return (y - ratio_target * x) ** 2

    constraints = [
        {
            "type": "eq",
            "fun": lambda var, remain=remain: var[0] + var[1] + var[2] + var[3] - remain,
        },
        {
            "type": "eq",
            "fun": lambda var, a=a_coeff, v=v: float(a[:4] @ var + a[4] * v),
        },
        {
            "type": "eq",
            "fun": lambda var, b=b_coeff, v=v: float(b[:4] @ var + b[4] * v),
        },
        {
            "type": "ineq",
            "fun": lambda var, lo=params.ratio_low: var[1] - lo * var[0],
        },
        {
            "type": "ineq",
            "fun": lambda var, hi=params.ratio_high: hi * var[0] - var[1],
        },
    ]
    bounds = [(0.0, remain)] * 4
    starts = []
    if x0 is not None:
        starts.append(np.clip(x0, 0, remain))
    # 与 Excel 基数接近的初值
    scale = remain / 94.0 if remain > 0 else 1.0
    starts.append(np.array([10.0, 20.0, 60.0, 4.0], dtype=float) * scale)
    starts.append(np.array([remain * 0.2, remain * 0.4, remain * 0.3, remain * 0.1]))
    starts.append(np.full(4, remain / 4.0))

    best = None
    best_obj = math.inf
    for start in starts:
        try:
            res = optimize.minimize(
                objective,
                start,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"ftol": 1e-12, "maxiter": 400, "disp": False},
            )
        except (ValueError, RuntimeError):
            continue
        if not res.success:
            continue
        var = np.maximum(res.x, 0.0)
        if var[0] + var[1] + var[2] + var[3] <= 0:
            continue
        if var[0] < 1e-8:
            continue
        ratio = var[1] / var[0]
        if not (params.ratio_low - 1e-5 <= ratio <= params.ratio_high + 1e-5):
            continue
        mass_res = abs(var.sum() - remain)
        s_res = abs(float(a_coeff[:4] @ var + a_coeff[4] * v))
        c_res = abs(float(b_coeff[:4] @ var + b_coeff[4] * v))
        if mass_res > 1e-4 or s_res > 1e-6 or c_res > 1e-6:
            continue
        obj = float(objective(var))
        if obj < best_obj:
            best_obj = obj
            best = var
    return best


def _chemistry_feasible(a_coeff: np.ndarray, b_coeff: np.ndarray, v: float, remain: float) -> bool:
    """忽略煤矸石/粉煤灰比例，仅检查质量+硫+钙+非负是否可行。"""
    c = np.zeros(4)
    a_eq = np.array(
        [
            [1.0, 1.0, 1.0, 1.0],
            [a_coeff[0], a_coeff[1], a_coeff[2], a_coeff[3]],
            [b_coeff[0], b_coeff[1], b_coeff[2], b_coeff[3]],
        ]
    )
    b_eq = np.array([remain, -a_coeff[4] * v, -b_coeff[4] * v])
    bounds = [(0.0, remain)] * 4
    try:
        res = optimize.linprog(
            c,
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )
    except Exception:
        return False
    return bool(res.success)


def _so3_available(mats: _MaterialSet) -> bool:
    return bool(np.any(mats.so3 > 1e-12))


def _oxide_masses(masses: np.ndarray, mats: _MaterialSet) -> tuple[float, float, float, float]:
    m_al = float(np.dot(masses, mats.al2o3) / 100.0)
    m_si = float(np.dot(masses, mats.sio2) / 100.0)
    m_ca = float(np.dot(masses, mats.cao) / 100.0)
    m_s = float(np.dot(masses, mats.so3) / 100.0)
    return m_al, m_si, m_ca, m_s


def _build_result(
    masses: np.ndarray,
    mats: _MaterialSet,
    params: ProcessParams,
    batch_mass: float,
) -> CalcResult:
    total = float(masses.sum())
    perc = masses / total * 100.0 if total > 0 else masses
    m_al, m_si, m_ca, m_s = _oxide_masses(masses, mats)
    n_al = m_al / params.mw_al2o3
    n_si = m_si / params.mw_sio2
    n_ca = m_ca / params.mw_cao
    n_s = m_s / params.mw_so3

    al_so3_actual = n_al / n_s if abs(n_s) > 1e-18 else math.inf
    theory_ca = params.al_coeff * n_al + params.si_coeff * n_si
    ca_actual = n_ca / theory_ca if abs(theory_ca) > 1e-18 else math.inf
    xy_actual = masses[1] / masses[0] if masses[0] > 1e-12 else math.inf
    v_percent = perc[4]

    def _check(name: str, actual: float, target: float, atol: float, detail: str) -> CheckItem:
        deviation = actual - target if math.isfinite(actual) else math.inf
        passed = math.isfinite(actual) and abs(actual - target) <= atol
        return CheckItem(
            name=name,
            actual=actual,
            target=target,
            deviation=deviation,
            passed=passed,
            detail=detail,
        )

    ratio_ok = math.isfinite(xy_actual) and params.ratio_low - 1e-6 <= xy_actual <= params.ratio_high + 1e-6
    checks = CalcChecks(
        total_mass=_check(
            "总质量",
            total,
            batch_mass,
            max(MASS_ATOL * 10, batch_mass * 1e-8),
            f"x+y+z+w+V = {total:.6f}，目标 {batch_mass:g}",
        ),
        al2o3_so3=_check(
            "Al₂O₃/SO₃",
            al_so3_actual,
            params.al2o3_so3_target,
            1e-4,
            "氧化物摩尔比",
        ),
        cao_ratio=_check(
            "CaO配比",
            ca_actual,
            params.cao_factor,
            1e-4,
            "n(CaO) / ((12/7)n(Al₂O₃) + 2 n(SiO₂))",
        ),
        gangue_flyash=CheckItem(
            name="粉煤灰/煤矸石",
            actual=xy_actual,
            target=params.gangue_flyash_target,
            deviation=xy_actual - params.gangue_flyash_target if math.isfinite(xy_actual) else math.inf,
            passed=ratio_ok,
            detail=f"允许范围 {params.ratio_low:.4f} ~ {params.ratio_high:.4f}",
        ),
        carbide_slag=_check(
            "电石渣",
            v_percent,
            params.carbide_slag_ratio * 100.0,
            1e-4,
            "占生料质量百分比",
        ),
    )

    percent_total = float(perc.sum())
    if percent_total > 100.0001:
        perc = perc * (100.0 / percent_total)
        percent_total = 100.0
    elif abs(percent_total - 100.0) <= 1e-8:
        percent_total = 100.0

    return CalcResult(
        masses=BlendMasses(
            coal_gangue=float(masses[0]),
            fly_ash=float(masses[1]),
            limestone=float(masses[2]),
            gypsum=float(masses[3]),
            carbide_slag=float(masses[4]),
            total=total,
        ),
        percents=BlendPercents(
            coal_gangue=float(perc[0]),
            fly_ash=float(perc[1]),
            limestone=float(perc[2]),
            gypsum=float(perc[3]),
            carbide_slag=float(perc[4]),
            total=percent_total,
        ),
        oxide_masses=OxideTotals(al2o3=m_al, sio2=m_si, cao=m_ca, so3=m_s),
        oxide_moles=OxideMoles(al2o3=n_al, sio2=n_si, cao=n_ca, so3=n_s),
        checks=checks,
        message="计算完成",
    )


def solve_blend(
    request: CalcRequest,
    *,
    rng: np.random.Generator | None = None,
    pollution: bool = True,
) -> CalcResult:
    params = request.params or default_params()
    mats = _materials_from_request(request)
    batch = float(request.batch_mass)
    v = params.carbide_slag_ratio * batch
    remain = batch - v
    if remain <= 0:
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)

    a_coeff = np.array([_sulfur_coeff(c, params) for c in mats.comps], dtype=float)
    b_coeff = np.array([_calcium_coeff(c, params) for c in mats.comps], dtype=float)

    if not _so3_available(mats):
        raise SolverError("no_so3", MSG_NO_SO3)

    rng = rng or np.random.default_rng()
    if pollution:
        preferred_ratio = _sample_polluted_ratio(params, rng)
    else:
        preferred_ratio = params.gangue_flyash_target

    xyzw = _solve_linear(a_coeff, b_coeff, v, remain, preferred_ratio)

    if xyzw is None:
        # 在允许带内多点尝试，尽量贴近受污染目标
        grid = np.linspace(params.ratio_low, params.ratio_high, 17)
        order = np.argsort(np.abs(grid - preferred_ratio))
        for idx in order:
            cand = _solve_linear(a_coeff, b_coeff, v, remain, float(grid[idx]))
            if cand is not None:
                xyzw = cand
                break

    if xyzw is None:
        xyzw = _solve_slsqp(a_coeff, b_coeff, v, remain, params, preferred_ratio, x0=None)

    if xyzw is None:
        chem_ok = _chemistry_feasible(a_coeff, b_coeff, v, remain)
        gypsum_so3 = mats.comps[3].so3
        if gypsum_so3 <= 1e-12 and abs(float(a_coeff @ np.array([remain / 4] * 4 + [v]))) > 1e-10:
            # 脱硫石膏无硫且线性硫约束明显偏离
            if not chem_ok:
                raise SolverError("no_so3", MSG_NO_SO3)
        if chem_ok:
            raise SolverError("ratio_infeasible", MSG_RATIO)
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)

    masses = _pack(xyzw, v)
    # 数值修正：保持 V 固定，其余按比例微调到总量 T
    others = masses[:4].sum()
    if others > 0 and abs(masses.sum() - batch) > MASS_ATOL:
        masses[:4] *= (batch - v) / others
        masses[4] = v

    if np.any(masses < -NONNEG_ATOL):
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)

    masses = np.maximum(masses, 0.0)
    result = _build_result(masses, mats, params, batch)

    if result.percents.total > 100.0001:
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)

    if not result.checks.total_mass.passed:
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)
    if not result.checks.carbide_slag.passed:
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)
    if not result.checks.al2o3_so3.passed or not result.checks.cao_ratio.passed:
        raise SolverError("no_feasible", MSG_NO_FEASIBLE)
    if not result.checks.gangue_flyash.passed:
        raise SolverError("ratio_infeasible", MSG_RATIO)
    return result
