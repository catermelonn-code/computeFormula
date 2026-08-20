# 煤矸石、粉煤灰提铝烧结原料配比计算系统

根据五种原料（煤矸石、粉煤灰、石灰石、脱硫石膏、电石渣）的化验成分，按工艺化学计量约束求解生料配比。

根目录下的 `test.html` 与 `附件2 原料物化特性数据集.xlsx` 仅为设计/算法参考，**不是本系统的运行文件**。

## 技术栈

- 前端：Vue 3 + TypeScript + Element Plus
- 后端：Python + FastAPI + Pydantic
- 算法：NumPy + SciPy
- 部署：Docker Compose + Nginx

## 快速启动

```bash
docker compose up --build
```

浏览器打开：http://localhost:8080

默认账号：

| 用户名 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员 |
| user | user123 | 普通用户 |

## 本地开发

后端：

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器为 http://localhost:5173，已将 `/api` 代理到后端。

## 算法约束

求解变量：煤矸石 \(x\)、粉煤灰 \(y\)、石灰石 \(z\)、脱硫石膏 \(w\)、电石渣 \(V\)。

- \(x + y + z + w + V = T\)（默认 \(T = 100\)）
- 电石渣固定为生料质量的 6%
- \(n(\mathrm{Al_2O_3}) / n(\mathrm{SO_3}) = 4\)（氧化物摩尔比，不是元素摩尔比）
- \(n(\mathrm{CaO}) / \left(\frac{12}{7}n(\mathrm{Al_2O_3}) + 2n(\mathrm{SiO_2})\right) = 1.03\)
- 粉煤灰/煤矸石质量比尽量接近 1:2，允许 ±2%（1.96 ~ 2.04）
- 全部质量非负；化验空值按 0；单行成分合计不得超过 100%
- 工艺参数（摩尔质量、目标比、电石渣比例等）可在系统中配置

输出为五种原料质量、质量百分比及自动校验项。百分比合计不超过 100%。

## 主要接口

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/calc/solve`
- `GET /api/calc/params` / `PUT /api/calc/params`（修改需管理员）
- `GET /api/history`
- `GET /api/users`（管理员）

## 运行测试

```bash
cd backend
pytest
```
