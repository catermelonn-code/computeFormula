from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OXIDE_FIELDS = (
    "sio2",
    "al2o3",
    "cao",
    "so3",
    "fe2o3",
    "mgo",
    "tio2",
    "na2o",
    "k2o",
)


def _empty_to_zero(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


class OxideComposition(BaseModel):
    """原料化验成分，质量百分比。空值按 0 处理。"""

    model_config = ConfigDict(populate_by_name=True)

    sio2: float = Field(0, ge=0, le=100, alias="SiO2")
    al2o3: float = Field(0, ge=0, le=100, alias="Al2O3")
    cao: float = Field(0, ge=0, le=100, alias="CaO")
    so3: float = Field(0, ge=0, le=100, alias="SO3")
    fe2o3: float = Field(0, ge=0, le=100, alias="Fe2O3")
    mgo: float = Field(0, ge=0, le=100, alias="MgO")
    tio2: float = Field(0, ge=0, le=100, alias="TiO2")
    na2o: float = Field(0, ge=0, le=100, alias="Na2O")
    k2o: float = Field(0, ge=0, le=100, alias="K2O")

    @field_validator(*OXIDE_FIELDS, mode="before")
    @classmethod
    def treat_blank_as_zero(cls, value: object) -> float:
        return _empty_to_zero(value)

    @property
    def row_sum(self) -> float:
        return sum(getattr(self, name) for name in OXIDE_FIELDS)

    def as_vector(self, keys: tuple[str, ...] = ("al2o3", "sio2", "cao", "so3")) -> list[float]:
        return [getattr(self, key) for key in keys]


class MaterialsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    coal_gangue: OxideComposition = Field(alias="煤矸石")
    fly_ash: OxideComposition = Field(alias="粉煤灰")
    limestone: OxideComposition = Field(alias="石灰石")
    gypsum: OxideComposition = Field(alias="脱硫石膏")
    carbide_slag: OxideComposition = Field(alias="电石渣")

    def named_items(self) -> list[tuple[str, OxideComposition]]:
        return [
            ("煤矸石", self.coal_gangue),
            ("粉煤灰", self.fly_ash),
            ("石灰石", self.limestone),
            ("脱硫石膏", self.gypsum),
            ("电石渣", self.carbide_slag),
        ]


class ProcessParams(BaseModel):
    al2o3_so3_target: float = Field(4.0, gt=0, description="Al2O3/SO3 目标摩尔比")
    cao_factor: float = Field(1.03, gt=0, description="CaO 配比系数")
    gangue_flyash_target: float = Field(2.0, gt=0, description="粉煤灰/煤矸石目标质量比")
    ratio_tolerance: float = Field(0.02, ge=0, le=0.5, description="比例允许偏差，0.02 表示 ±2%")
    carbide_slag_ratio: float = Field(0.06, gt=0, lt=1, description="电石渣占生料质量比例")
    mw_al2o3: float = Field(101.96, gt=0)
    mw_sio2: float = Field(60.08, gt=0)
    mw_cao: float = Field(56.08, gt=0)
    mw_so3: float = Field(80.06, gt=0)
    al_coeff: float = Field(12 / 7, gt=0, description="理论配钙中 Al2O3 摩尔系数")
    si_coeff: float = Field(2.0, gt=0, description="理论配钙中 SiO2 摩尔系数")

    @property
    def ratio_low(self) -> float:
        return self.gangue_flyash_target * (1.0 - self.ratio_tolerance)

    @property
    def ratio_high(self) -> float:
        return self.gangue_flyash_target * (1.0 + self.ratio_tolerance)


class CalcRequest(BaseModel):
    materials: MaterialsInput
    batch_mass: float = Field(100.0, gt=0, description="生产批次总质量 T")
    params: Optional[ProcessParams] = None

    @model_validator(mode="after")
    def validate_row_sums(self) -> "CalcRequest":
        overflow = [
            name for name, comp in self.materials.named_items() if comp.row_sum > 100.0001
        ]
        if overflow:
            raise ValueError(f"以下原料化验成分行合计超过 100%：{'、'.join(overflow)}")
        has_data = any(
            comp.row_sum > 0 for _, comp in self.materials.named_items()
        )
        if not has_data:
            raise ValueError("请至少输入一种原料的化验成分")
        return self


class BlendMasses(BaseModel):
    coal_gangue: float
    fly_ash: float
    limestone: float
    gypsum: float
    carbide_slag: float
    total: float


class BlendPercents(BaseModel):
    coal_gangue: float
    fly_ash: float
    limestone: float
    gypsum: float
    carbide_slag: float
    total: float


class OxideTotals(BaseModel):
    al2o3: float
    sio2: float
    cao: float
    so3: float


class OxideMoles(BaseModel):
    al2o3: float
    sio2: float
    cao: float
    so3: float


class CheckItem(BaseModel):
    name: str
    actual: float
    target: float
    deviation: float
    passed: bool
    detail: str = ""


class CalcChecks(BaseModel):
    total_mass: CheckItem
    al2o3_so3: CheckItem
    cao_ratio: CheckItem
    gangue_flyash: CheckItem
    carbide_slag: CheckItem


class CalcResult(BaseModel):
    masses: BlendMasses
    percents: BlendPercents
    oxide_masses: OxideTotals
    oxide_moles: OxideMoles
    checks: CalcChecks
    message: str = "计算完成"


class CalcResponse(BaseModel):
    success: bool
    result: Optional[CalcResult] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    history_id: Optional[str] = None


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    role: str = Field(default="user")

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class HistoryOut(BaseModel):
    id: str
    created_at: datetime
    username: str
    success: bool
    error_message: Optional[str]
    coal_gangue: Optional[float]
    fly_ash: Optional[float]
    limestone: Optional[float]
    gypsum: Optional[float]
    carbide_slag: Optional[float]
    al_so3_ratio: Optional[float]
    ca_ratio: Optional[float]
    xy_ratio: Optional[float]
    request: dict
    result: Optional[dict] = None
