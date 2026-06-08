import assert from "node:assert/strict";
import test from "node:test";

import { formatBusinessNumber, formatInteger, formatRate } from "./formatters.js";

test("formatInteger renders Chinese thousands separators", () => {
  assert.equal(formatInteger(12226000), "12,226,000");
});

test("formatRate keeps missing 5S as 未提供", () => {
  assert.equal(formatRate(null), "未提供");
  assert.equal(formatRate(0.1413), "14.1%");
});

test("formatBusinessNumber renders six-digit and larger values as 万", () => {
  assert.equal(formatBusinessNumber(12226000), "1222万");
  assert.equal(formatBusinessNumber(100000), "10万");
  assert.equal(formatBusinessNumber(99999), "99,999");
});
