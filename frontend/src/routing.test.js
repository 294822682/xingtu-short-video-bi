import assert from "node:assert/strict";
import test from "node:test";

import { routeFromPath } from "./routing.js";

test("root remains backward-compatible with the xingtu dashboard", () => {
  const route = routeFromPath("/");

  assert.equal(route.view, "dashboard");
  assert.equal(route.module.slug, "xingtu");
});

test("admin root remains backward-compatible with xingtu maintenance", () => {
  const route = routeFromPath("/admin");

  assert.equal(route.view, "admin");
  assert.equal(route.module.slug, "xingtu");
});

test("hub and oae paths resolve to separate views", () => {
  assert.equal(routeFromPath("/hub").view, "hub");
  assert.equal(routeFromPath("/oae").module.slug, "oae");
  assert.equal(routeFromPath("/admin/oae").module.slug, "oae");
});
