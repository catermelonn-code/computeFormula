import axios from "axios";
import { ElMessage } from "element-plus";

const http = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("bf_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("；")
          : error.message || "请求失败";
    if (status === 401) {
      localStorage.removeItem("bf_token");
      localStorage.removeItem("bf_user");
      if (!window.location.hash.includes("login") && window.location.pathname !== "/") {
        ElMessage.warning("请先登录");
      }
    } else if (status !== 401) {
      ElMessage.error(message);
    }
    return Promise.reject(error);
  },
);

export default http;
