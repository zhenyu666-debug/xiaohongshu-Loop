import axios from "axios";

const API_BASE = "/api";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

export default api;
