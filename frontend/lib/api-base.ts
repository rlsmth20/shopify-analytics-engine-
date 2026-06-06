const LOCAL_API_BASE = "http://localhost:8000";
const PRODUCTION_API_BASE = "https://api.skubase.io";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NODE_ENV === "development" ? LOCAL_API_BASE : PRODUCTION_API_BASE);
