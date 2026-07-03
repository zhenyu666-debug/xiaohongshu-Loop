import axios from "axios";

const http = axios.create({
  baseURL: "/api",
  timeout: 15_000,
});

http.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    const url = err?.config?.url ?? "";
    if (status === 401) {
      // auth handler hook point
    }
    const msg = err?.response?.data?.detail ?? err?.message ?? "请求失败";
    err.userMessage = `[${status ?? "?"}] ${url}: ${msg}`;
    return Promise.reject(err);
  },
);

export default http;