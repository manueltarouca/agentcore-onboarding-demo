import { describe, expect, it } from "vitest";
import { LANE, nodePosition } from "./layout";

const invocations = [1, 1, 1, 1, 1, 1, 2, 2, 2, 2];

describe("nodePosition", () => {
  it("puts each Runtime invocation on its own lane, read left to right", () => {
    const first = nodePosition(0, invocations);
    const sixth = nodePosition(5, invocations);
    const seventh = nodePosition(6, invocations);

    expect(sixth.y).toBe(first.y);
    expect(sixth.x).toBeGreaterThan(first.x);
    expect(seventh.y).toBe(first.y + LANE.height);
    expect(seventh.x).toBe(first.x);
  });
});
