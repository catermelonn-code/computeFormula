<template>
  <div class="app-shell">
    <div class="app-container">
      <header class="app-header">
        <div class="brand">
          <div class="brand-icon">⚙</div>
          <div>
            <h1>物料配比<span>平台</span></h1>
            <p class="sub">煤矸石、粉煤灰提铝烧结原料配比计算系统</p>
          </div>
        </div>
        <div class="header-actions">
          <div class="user-badge">
            <span>👤</span>
            <span>{{ auth.user?.username || "未登录" }}</span>
            <el-tag v-if="auth.user" size="small" round type="primary">
              {{ auth.user.role === "admin" ? "管理员" : "用户" }}
            </el-tag>
          </div>
          <el-button v-if="!auth.loggedIn" round @click="loginVisible = true">登录</el-button>
          <el-button v-else round @click="onLogout">登出</el-button>
          <el-button v-if="auth.isAdmin" type="primary" round @click="openUsers">用户管理</el-button>
          <el-button v-if="auth.loggedIn" round @click="openParams">工艺参数</el-button>
        </div>
      </header>

      <div class="main-grid">
        <section>
          <div class="panel">
            <div class="panel-title">
              物料化学成分
              <span class="badge">% 质量分数</span>
              <span style="margin-left: auto; font-size: 13px; font-weight: 400; color: var(--text-secondary)">
                {{ statusText }}
              </span>
            </div>
            <div class="input-table-wrap">
              <table class="input-table">
                <thead>
                  <tr>
                    <th style="text-align: left; padding-left: 8px">物料</th>
                    <th v-for="ox in visibleOxides" :key="ox.key">{{ ox.label }}</th>
                    <th>行合计</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="mat in MATERIALS" :key="mat.key">
                    <td class="row-label">{{ mat.label }}</td>
                    <td v-for="ox in visibleOxides" :key="ox.key">
                      <el-input
                        v-model="materials[mat.key][ox.key]"
                        size="small"
                        placeholder="0"
                        :disabled="!auth.loggedIn"
                        @input="onInputChanged"
                      />
                    </td>
                    <td>
                      <span :class="{ 'row-sum': true, warn: rowSum(mat.key) > 100 }">
                        {{ rowSum(mat.key).toFixed(2) }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="input-actions">
              <el-button type="primary" round :disabled="!auth.loggedIn" :loading="calculating" @click="calculate">
                计算配比
              </el-button>
              <el-button round :disabled="!auth.loggedIn" @click="resetInputs">重置</el-button>
              <el-button round :disabled="!auth.loggedIn" @click="loadExample">加载示例</el-button>
              <el-checkbox v-model="showExtra" :disabled="!auth.loggedIn">更多成分</el-checkbox>
              <span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px">
                批次质量 T
                <el-input-number v-model="batchMass" :min="0.001" :step="10" size="small" :disabled="!auth.loggedIn" />
                kg
              </span>
              <span class="hint">{{ hint }}</span>
            </div>
          </div>
        </section>

        <aside class="output-panel">
          <div class="panel">
            <div class="panel-title">
              配比输出
              <span class="badge">质量 / 配方比例</span>
            </div>
            <div class="output-grid">
              <div v-for="item in outputItems" :key="item.key" class="output-item" :class="{ span2: item.span }">
                <span class="label">{{ item.label }}</span>
                <span class="value" :class="{ placeholder: result == null }">
                  {{ formatMass(item.key) }}
                </span>
                <span class="sub">{{ formatPercent(item.key) }}</span>
              </div>
            </div>

            <div class="check-summary">
              <div v-for="ck in checkRows" :key="ck.label" class="check-item">
                <span>{{ ck.label }}</span>
                <span>
                  <span class="ck-value">{{ ck.value }}</span>
                  <span :class="ck.ok === null ? '' : ck.ok ? 'ck-ok' : 'ck-err'">
                    {{ ck.ok === null ? " ⚪" : ck.ok ? " ✅" : " ❌" }}
                  </span>
                </span>
              </div>
            </div>

            <div v-if="result" class="oxide-detail">
              <div>Al₂O₃ 总质量 {{ result.oxide_masses.al2o3.toFixed(4) }}</div>
              <div>摩尔 {{ result.oxide_moles.al2o3.toExponential(3) }}</div>
              <div>SiO₂ 总质量 {{ result.oxide_masses.sio2.toFixed(4) }}</div>
              <div>摩尔 {{ result.oxide_moles.sio2.toExponential(3) }}</div>
              <div>CaO 总质量 {{ result.oxide_masses.cao.toFixed(4) }}</div>
              <div>摩尔 {{ result.oxide_moles.cao.toExponential(3) }}</div>
              <div>SO₃ 总质量 {{ result.oxide_masses.so3.toFixed(4) }}</div>
              <div>摩尔 {{ result.oxide_moles.so3.toExponential(3) }}</div>
            </div>

            <div class="output-note">{{ note }}</div>
          </div>
        </aside>
      </div>

      <section class="history-section">
        <div class="history-header">
          <div class="panel-title">
            历史记录
            <span class="badge">{{ history.length }} 条</span>
          </div>
          <div style="display: flex; gap: 8px">
            <el-button round size="small" :disabled="!auth.loggedIn" @click="loadHistory">刷新</el-button>
            <el-button round size="small" type="danger" :disabled="!auth.loggedIn" @click="clearHistory">
              清空
            </el-button>
          </div>
        </div>
        <div class="panel" style="padding: 12px 16px 16px">
          <el-table :data="history" size="small" empty-text="暂无历史记录" style="width: 100%">
            <el-table-column label="时间" min-width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column v-if="auth.isAdmin" prop="username" label="用户" width="100" />
            <el-table-column label="煤矸石" min-width="90">
              <template #default="{ row }">{{ fmt(row.coal_gangue) }}</template>
            </el-table-column>
            <el-table-column label="粉煤灰" min-width="90">
              <template #default="{ row }">{{ fmt(row.fly_ash) }}</template>
            </el-table-column>
            <el-table-column label="石灰石" min-width="90">
              <template #default="{ row }">{{ fmt(row.limestone) }}</template>
            </el-table-column>
            <el-table-column label="脱硫石膏" min-width="90">
              <template #default="{ row }">{{ fmt(row.gypsum) }}</template>
            </el-table-column>
            <el-table-column label="电石渣" min-width="90">
              <template #default="{ row }">{{ fmt(row.carbide_slag) }}</template>
            </el-table-column>
            <el-table-column label="Al₂O₃/SO₃" min-width="100">
              <template #default="{ row }">{{ fmt(row.al_so3_ratio) }}</template>
            </el-table-column>
            <el-table-column label="CaO配比" min-width="90">
              <template #default="{ row }">{{ fmt(row.ca_ratio) }}</template>
            </el-table-column>
            <el-table-column label="y/x" min-width="80">
              <template #default="{ row }">{{ fmt(row.xy_ratio) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <div class="app-footer">煤矸石、粉煤灰提铝烧结原料配比计算系统 v1.0</div>
    </div>

    <el-dialog v-model="loginVisible" title="登录" width="420px">
      <el-form label-position="top" @submit.prevent="doLogin">
        <el-form-item label="用户名">
          <el-input v-model="loginForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="loginForm.password" type="password" show-password @keyup.enter="doLogin" />
        </el-form-item>
      </el-form>
      <p v-if="loginError" style="color: var(--danger); margin: 0 0 8px">{{ loginError }}</p>
      <template #footer>
        <el-button @click="loginVisible = false">取消</el-button>
        <el-button type="primary" :loading="loginLoading" @click="doLogin">登录</el-button>
      </template>
      <p style="margin: 0; font-size: 13px; color: var(--text-secondary)">
        默认管理员：admin / admin123 · 普通用户：user / user123
      </p>
    </el-dialog>

    <el-dialog v-model="usersVisible" title="用户管理" width="620px">
      <div style="display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap">
        <el-input v-model="newUser.username" placeholder="新用户名" style="width: 140px" />
        <el-input v-model="newUser.password" placeholder="密码" style="width: 140px" />
        <el-select v-model="newUser.role" style="width: 110px">
          <el-option label="用户" value="user" />
          <el-option label="管理员" value="admin" />
        </el-select>
        <el-button type="success" @click="addUser">添加</el-button>
      </div>
      <el-table :data="users" size="small">
        <el-table-column prop="username" label="用户名" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">{{ row.role === "admin" ? "管理员" : "用户" }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              v-if="row.id !== auth.user?.id"
              type="danger"
              link
              @click="removeUser(row.id)"
            >
              删除
            </el-button>
            <span v-else style="color: var(--text-light)">当前</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="paramsVisible" title="工艺参数" width="560px">
      <el-form v-if="params" label-width="210px">
        <el-form-item label="Al₂O₃/SO₃ 目标摩尔比">
          <el-input-number v-model="params.al2o3_so3_target" :step="0.1" :min="0.001" />
        </el-form-item>
        <el-form-item label="CaO 配比系数">
          <el-input-number v-model="params.cao_factor" :step="0.01" :min="0.001" />
        </el-form-item>
        <el-form-item label="粉煤灰/煤矸石目标比例">
          <el-input-number v-model="params.gangue_flyash_target" :step="0.1" :min="0.001" />
        </el-form-item>
        <el-form-item label="比例允许偏差">
          <el-input-number v-model="params.ratio_tolerance" :step="0.01" :min="0" :max="0.5" />
        </el-form-item>
        <el-form-item label="电石渣固定比例">
          <el-input-number v-model="params.carbide_slag_ratio" :step="0.01" :min="0.001" :max="0.99" />
        </el-form-item>
        <el-form-item label="Al₂O₃ 摩尔质量">
          <el-input-number v-model="params.mw_al2o3" :step="0.01" :min="0.001" />
        </el-form-item>
        <el-form-item label="SiO₂ 摩尔质量">
          <el-input-number v-model="params.mw_sio2" :step="0.01" :min="0.001" />
        </el-form-item>
        <el-form-item label="CaO 摩尔质量">
          <el-input-number v-model="params.mw_cao" :step="0.01" :min="0.001" />
        </el-form-item>
        <el-form-item label="SO₃ 摩尔质量">
          <el-input-number v-model="params.mw_so3" :step="0.01" :min="0.001" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paramsVisible = false">关闭</el-button>
        <el-button v-if="auth.isAdmin" type="primary" @click="saveParams">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import {
  EXTRA_OXIDES,
  MAIN_OXIDES,
  MATERIALS,
  emptyMaterials,
  type CalcResult,
  type HistoryItem,
  type MaterialKey,
  type MaterialsMap,
  type OxideComposition,
  type ProcessParams,
  type UserInfo,
} from "@/types";

const auth = useAuthStore();
const materials = reactive<MaterialsMap>(emptyMaterials());
const batchMass = ref(100);
const showExtra = ref(false);
const calculating = ref(false);
const result = ref<CalcResult | null>(null);
const history = ref<HistoryItem[]>([]);
const users = ref<UserInfo[]>([]);
const params = ref<ProcessParams | null>(null);
const statusText = ref("● 就绪");
const hint = ref("输入成分后点击计算");
const note = ref("请先输入物料成分，点击「计算配比」");

const loginVisible = ref(false);
const loginLoading = ref(false);
const loginError = ref("");
const loginForm = reactive({ username: "admin", password: "admin123" });
const usersVisible = ref(false);
const paramsVisible = ref(false);
const newUser = reactive({ username: "", password: "", role: "user" });

const visibleOxides = computed(() => (showExtra.value ? [...MAIN_OXIDES, ...EXTRA_OXIDES] : MAIN_OXIDES));

const outputItems = [
  { key: "coal_gangue" as const, label: "煤矸石 (x)", span: false },
  { key: "fly_ash" as const, label: "粉煤灰 (y)", span: false },
  { key: "limestone" as const, label: "石灰石 (z)", span: false },
  { key: "gypsum" as const, label: "脱硫石膏 (w)", span: false },
  { key: "carbide_slag" as const, label: "电石渣 (V)", span: true },
];

const checkRows = computed(() => {
  const c = result.value?.checks;
  if (!c) {
    return [
      { label: "总质量", value: "—", ok: null as boolean | null },
      { label: "Al₂O₃/SO₃", value: "—", ok: null },
      { label: "CaO配比", value: "—", ok: null },
      { label: "粉煤灰/煤矸石", value: "—", ok: null },
      { label: "电石渣", value: "—", ok: null },
    ];
  }
  const f = (n: number) => (Number.isFinite(n) ? n.toFixed(4) : "—");
  return [
    { label: "总质量", value: `${f(c.total_mass.actual)} / ${f(c.total_mass.target)}`, ok: c.total_mass.passed },
    {
      label: "Al₂O₃/SO₃",
      value: `${f(c.al2o3_so3.actual)} (目标 ${f(c.al2o3_so3.target)}，偏差 ${f(c.al2o3_so3.deviation)})`,
      ok: c.al2o3_so3.passed,
    },
    {
      label: "CaO配比",
      value: `${f(c.cao_ratio.actual)} (目标 ${f(c.cao_ratio.target)}，偏差 ${f(c.cao_ratio.deviation)})`,
      ok: c.cao_ratio.passed,
    },
    {
      label: "粉煤灰/煤矸石",
      value: `${f(c.gangue_flyash.actual)}  ${c.gangue_flyash.detail}`,
      ok: c.gangue_flyash.passed,
    },
    {
      label: "电石渣",
      value: `${f(c.carbide_slag.actual)}% / ${f(c.carbide_slag.target)}%`,
      ok: c.carbide_slag.passed,
    },
  ];
});

function rowSum(key: MaterialKey): number {
  const row = materials[key];
  return [...MAIN_OXIDES, ...EXTRA_OXIDES].reduce((sum, ox) => sum + toNum(row[ox.key]), 0);
}

function toNum(v: number | "" | undefined): number {
  if (v === "" || v === undefined || v === null) return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function payloadMaterials() {
  const out: Record<string, Record<string, number>> = {};
  for (const mat of MATERIALS) {
    const row: Record<string, number> = {};
    for (const ox of [...MAIN_OXIDES, ...EXTRA_OXIDES]) {
      row[ox.key] = toNum(materials[mat.key][ox.key]);
    }
    out[mat.key] = row;
  }
  return out;
}

function fillMaterials(src: Record<string, Record<string, number>>) {
  for (const mat of MATERIALS) {
    const row = src[mat.key] || {};
    const target = emptyMaterials()[mat.key];
    for (const ox of [...MAIN_OXIDES, ...EXTRA_OXIDES]) {
      const v = row[ox.key];
      (target as OxideComposition)[ox.key] = v === undefined || v === null ? "" : v;
    }
    Object.assign(materials[mat.key], target);
  }
}

function onInputChanged() {
  if (result.value) {
    result.value = null;
    note.value = "输入已更改，请重新计算";
  }
  statusText.value = "● 已修改";
}

function formatMass(key: MaterialKey) {
  if (!result.value) return "—";
  return result.value.masses[key].toFixed(4);
}

function formatPercent(key: MaterialKey) {
  if (!result.value) return "配方比例 —";
  return `配方比例 ${result.value.percents[key].toFixed(4)}%`;
}

function fmt(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(4);
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString("zh-CN", { hour12: false });
}

async function doLogin() {
  loginLoading.value = true;
  loginError.value = "";
  try {
    await auth.login(loginForm.username.trim(), loginForm.password);
    loginVisible.value = false;
    statusText.value = "● 已登录";
    note.value = "请点击「计算配比」";
    await Promise.all([loadHistory(), loadParams()]);
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    loginError.value = detail || "用户名或密码错误，请重试";
  } finally {
    loginLoading.value = false;
  }
}

async function onLogout() {
  try {
    await ElMessageBox.confirm("确认登出吗？", "提示");
  } catch {
    return;
  }
  auth.logout();
  result.value = null;
  history.value = [];
  statusText.value = "⛔ 未登录";
  note.value = "已登出，请登录后使用";
}

async function calculate() {
  if (!auth.loggedIn) {
    ElMessage.warning("请先登录");
    return;
  }
  for (const mat of MATERIALS) {
    if (rowSum(mat.key) > 100.0001) {
      ElMessage.error(`${mat.label} 化验成分行合计超过 100%，请检查输入`);
      return;
    }
  }
  calculating.value = true;
  try {
    const { data } = await http.post("/calc/solve", {
      materials: payloadMaterials(),
      batch_mass: batchMass.value,
    });
    if (!data.success) {
      result.value = null;
      note.value = data.error_message || "计算失败";
      ElMessage.error(data.error_message || "当前原料无法求得可行配比");
      await loadHistory();
      return;
    }
    result.value = data.result;
    statusText.value = "● 已计算";
    note.value = `计算完成  ·  ${new Date().toLocaleString()}`;
    ElMessage.success("计算完成");
    await loadHistory();
  } finally {
    calculating.value = false;
  }
}

async function resetInputs() {
  try {
    await ElMessageBox.confirm("确认重置所有输入数据吗？", "提示");
  } catch {
    return;
  }
  Object.assign(materials, emptyMaterials());
  result.value = null;
  note.value = "已重置，请重新输入";
  statusText.value = "● 已重置";
}

async function loadExample() {
  const { data } = await http.get("/calc/example");
  fillMaterials(data.materials);
  batchMass.value = data.batch_mass || 100;
  result.value = null;
  note.value = "已加载示例数据，点击「计算配比」";
  statusText.value = "● 示例已加载";
}

async function loadHistory() {
  if (!auth.loggedIn) return;
  const { data } = await http.get("/history");
  history.value = data;
}

async function clearHistory() {
  try {
    await ElMessageBox.confirm("确认清空历史记录吗？", "提示", { type: "warning" });
  } catch {
    return;
  }
  await http.delete("/history");
  await loadHistory();
}

async function openUsers() {
  const { data } = await http.get("/users");
  users.value = data;
  usersVisible.value = true;
}

async function addUser() {
  if (!newUser.username.trim() || !newUser.password.trim()) {
    ElMessage.warning("用户名和密码不能为空");
    return;
  }
  await http.post("/users", newUser);
  newUser.username = "";
  newUser.password = "";
  newUser.role = "user";
  const { data } = await http.get("/users");
  users.value = data;
  ElMessage.success("已添加");
}

async function removeUser(id: string) {
  try {
    await ElMessageBox.confirm("确认删除该用户吗？", "提示", { type: "warning" });
  } catch {
    return;
  }
  await http.delete(`/users/${id}`);
  const { data } = await http.get("/users");
  users.value = data;
}

async function loadParams() {
  if (!auth.loggedIn) return;
  const { data } = await http.get("/calc/params");
  params.value = data;
}

async function openParams() {
  await loadParams();
  paramsVisible.value = true;
}

async function saveParams() {
  if (!params.value) return;
  const { data } = await http.put("/calc/params", params.value);
  params.value = data;
  ElMessage.success("工艺参数已保存");
  paramsVisible.value = false;
}

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    if (auth.loggedIn && !calculating.value) calculate();
  }
}

onMounted(async () => {
  window.addEventListener("keydown", onKeydown);
  if (auth.loggedIn) {
    await auth.refreshMe();
    if (auth.loggedIn) {
      statusText.value = "● 已登录，请输入数据";
      note.value = "请点击「计算配比」";
      await Promise.all([loadHistory(), loadParams(), loadExample()]);
    }
  } else {
    statusText.value = "⛔ 未登录";
    note.value = "请登录后使用";
    loginVisible.value = true;
  }
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
});
</script>

<style scoped>
:deep(.el-input) {
  width: 72px;
}
:deep(.el-input__wrapper) {
  padding: 1px 6px;
}
:deep(.el-input__inner) {
  text-align: center;
}
</style>
