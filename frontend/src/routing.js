import { moduleForSlug } from "./modules.js";

export function routeFromPath(pathname) {
  const path = normalizePath(pathname);
  if (path === "/hub") return { view: "hub", module: null };
  if (path === "/admin" || path === "/admin/xingtu") return { view: "admin", module: moduleForSlug("xingtu") };
  if (path === "/admin/oae") return { view: "admin", module: moduleForSlug("oae") };
  if (path === "/oae") return { view: "dashboard", module: moduleForSlug("oae") };
  return { view: "dashboard", module: moduleForSlug("xingtu") };
}

function normalizePath(pathname) {
  const clean = pathname.replace(/\/+$/, "");
  return clean || "/";
}
