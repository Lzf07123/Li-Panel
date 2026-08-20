import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AsyncButton } from "./AsyncButton";

describe("AsyncButton 语义", () => {
  it("默认显式 type=button，避免表单内误提交", () => {
    render(<AsyncButton status="idle">保存</AsyncButton>);
    expect(screen.getByRole("button", { name: "保存" })).toHaveAttribute(
      "type",
      "button",
    );
  });
  it("调用方传入 type=submit 时保留", () => {
    render(
      <AsyncButton type="submit" status="idle">
        提交
      </AsyncButton>,
    );
    expect(screen.getByRole("button", { name: "提交" })).toHaveAttribute(
      "type",
      "submit",
    );
  });
});
