import { defineStore } from "pinia";
import { computed, ref } from "vue";
import http from "@/api/http";
import type { UserInfo } from "@/types";

export const useAuthStore = defineStore("auth", () => {
  const token = ref(localStorage.getItem("bf_token") || "");
  const user = ref<UserInfo | null>(
    (() => {
      const raw = localStorage.getItem("bf_user");
      if (!raw) return null;
      try {
        return JSON.parse(raw) as UserInfo;
      } catch {
        return null;
      }
    })(),
  );

  const loggedIn = computed(() => Boolean(token.value && user.value));
  const isAdmin = computed(() => user.value?.role === "admin");

  async function login(username: string, password: string) {
    const { data } = await http.post("/auth/login", { username, password });
    token.value = data.access_token;
    user.value = data.user;
    localStorage.setItem("bf_token", token.value);
    localStorage.setItem("bf_user", JSON.stringify(user.value));
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem("bf_token");
    localStorage.removeItem("bf_user");
  }

  async function refreshMe() {
    if (!token.value) return;
    try {
      const { data } = await http.get("/auth/me");
      user.value = data;
      localStorage.setItem("bf_user", JSON.stringify(data));
    } catch {
      logout();
    }
  }

  return { token, user, loggedIn, isAdmin, login, logout, refreshMe };
});
