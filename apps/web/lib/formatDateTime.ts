/** 赛程统一按北京时间展示（与 FIFA 官网「本地时间」对中国用户一致） */
export const DISPLAY_TZ = "Asia/Shanghai";

/** 将 API 返回的时间解析为 UTC（无 Z 后缀时按 UTC 处理） */
export function parseUtc(iso: string): Date {
  const normalized =
    iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  return new Date(normalized);
}

export function formatKickoff(iso: string): string {
  return parseUtc(iso).toLocaleString("zh-CN", {
    timeZone: DISPLAY_TZ,
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatDateTime(iso: string): string {
  return parseUtc(iso).toLocaleString("zh-CN", {
    timeZone: DISPLAY_TZ,
    hour12: false,
  });
}
