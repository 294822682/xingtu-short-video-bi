import assert from "node:assert/strict";
import test from "node:test";

import { dashboardHeaderStatusText } from "./headerStatus.js";

test("dashboard header status uses business text instead of source metadata", () => {
  const text = dashboardHeaderStatusText({
    status: "live",
    overview: {
      source_file_name: "26年账号曝光统计表-星途新媒体（统计台账）.xlsx",
      generated_at: "2026-06-12T11:32:51",
    },
  });

  assert.equal(text, "当前数据已就绪");
  assert.doesNotMatch(text, /\\.xlsx|2026-06-12T11:32:51|source_file_name|generated_at|sheet|字段来源|缺失字段/);
});

test("dashboard header status keeps sample data state business-readable", () => {
  assert.equal(dashboardHeaderStatusText({ status: "using-default", overview: {} }), "样例数据");
});
