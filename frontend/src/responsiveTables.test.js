import assert from "node:assert/strict";
import test from "node:test";

import { accountTableColumns, actorTableColumns } from "./responsiveTables.js";

test("account table exposes business labels for narrow embedded views", () => {
  assert.deepEqual(
    accountTableColumns.map((column) => column.label),
    ["平台", "账号名称", "发布条数", "曝光量", "平均曝光", "5S 完播率", "有演员视频"]
  );
});

test("actor table exposes business labels for narrow embedded views", () => {
  assert.deepEqual(
    actorTableColumns.map((column) => column.label),
    ["视频演员", "拍摄条数", "参与账号数", "贡献曝光量", "参与账号"]
  );
});
