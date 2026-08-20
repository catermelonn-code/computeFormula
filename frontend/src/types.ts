export interface OxideComposition {
  SiO2: number | "";
  Al2O3: number | "";
  CaO: number | "";
  SO3: number | "";
  Fe2O3: number | "";
  MgO: number | "";
  TiO2: number | "";
  Na2O: number | "";
  K2O: number | "";
}

export type MaterialKey =
  | "coal_gangue"
  | "fly_ash"
  | "limestone"
  | "gypsum"
  | "carbide_slag";

export type MaterialsMap = Record<MaterialKey, OxideComposition>;

export interface ProcessParams {
  al2o3_so3_target: number;
  cao_factor: number;
  gangue_flyash_target: number;
  ratio_tolerance: number;
  carbide_slag_ratio: number;
  mw_al2o3: number;
  mw_sio2: number;
  mw_cao: number;
  mw_so3: number;
  al_coeff: number;
  si_coeff: number;
}

export interface CheckItem {
  name: string;
  actual: number;
  target: number;
  deviation: number;
  passed: boolean;
  detail: string;
}

export interface CalcResult {
  masses: Record<MaterialKey | "total", number>;
  percents: Record<MaterialKey | "total", number>;
  oxide_masses: { al2o3: number; sio2: number; cao: number; so3: number };
  oxide_moles: { al2o3: number; sio2: number; cao: number; so3: number };
  checks: {
    total_mass: CheckItem;
    al2o3_so3: CheckItem;
    cao_ratio: CheckItem;
    gangue_flyash: CheckItem;
    carbide_slag: CheckItem;
  };
  message: string;
}

export interface CalcResponse {
  success: boolean;
  result: CalcResult | null;
  error_code: string | null;
  error_message: string | null;
  history_id: string | null;
}

export interface UserInfo {
  id: string;
  username: string;
  role: "admin" | "user" | string;
  created_at: string;
}

export interface HistoryItem {
  id: string;
  created_at: string;
  username: string;
  success: boolean;
  error_message: string | null;
  coal_gangue: number | null;
  fly_ash: number | null;
  limestone: number | null;
  gypsum: number | null;
  carbide_slag: number | null;
  al_so3_ratio: number | null;
  ca_ratio: number | null;
  xy_ratio: number | null;
  request: unknown;
  result: CalcResult | null;
}

export const MATERIALS: { key: MaterialKey; label: string }[] = [
  { key: "coal_gangue", label: "煤矸石" },
  { key: "fly_ash", label: "粉煤灰" },
  { key: "limestone", label: "石灰石" },
  { key: "gypsum", label: "脱硫石膏" },
  { key: "carbide_slag", label: "电石渣" },
];

export const MAIN_OXIDES = [
  { key: "SiO2" as const, label: "SiO₂" },
  { key: "Al2O3" as const, label: "Al₂O₃" },
  { key: "CaO" as const, label: "CaO" },
  { key: "Fe2O3" as const, label: "Fe₂O₃" },
  { key: "MgO" as const, label: "MgO" },
  { key: "SO3" as const, label: "SO₃" },
];

export const EXTRA_OXIDES = [
  { key: "TiO2" as const, label: "TiO₂" },
  { key: "Na2O" as const, label: "Na₂O" },
  { key: "K2O" as const, label: "K₂O" },
];

export function emptyOxide(): OxideComposition {
  return {
    SiO2: "",
    Al2O3: "",
    CaO: "",
    SO3: "",
    Fe2O3: "",
    MgO: "",
    TiO2: "",
    Na2O: "",
    K2O: "",
  };
}

export function emptyMaterials(): MaterialsMap {
  return {
    coal_gangue: emptyOxide(),
    fly_ash: emptyOxide(),
    limestone: emptyOxide(),
    gypsum: emptyOxide(),
    carbide_slag: emptyOxide(),
  };
}
