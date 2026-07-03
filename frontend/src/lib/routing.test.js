import { describe, expect, test } from "vitest";
import { parseRoute, routeHash } from "./routing.js";

const VIEWS = new Set(["picks", "fighters", "friends", "lab"]);
const parse = (hash) => parseRoute(hash, VIEWS, "picks");

describe("parseRoute", () => {
  test("empty hash falls back to the landing view", () => {
    expect(parse("")).toEqual({ view: "picks", param: "" });
    expect(parse("#/")).toEqual({ view: "picks", param: "" });
  });

  test("plain view routes", () => {
    expect(parse("#/lab")).toEqual({ view: "lab", param: "" });
    expect(parse("#/friends")).toEqual({ view: "friends", param: "" });
  });

  test("unknown views fall back without leaking the param", () => {
    expect(parse("#/nope")).toEqual({ view: "picks", param: "" });
    expect(parse("#/nope/anything")).toEqual({ view: "picks", param: "" });
  });

  test("params decode percent-encoding", () => {
    expect(parse("#/fighters/Max%20Holloway")).toEqual({
      view: "fighters",
      param: "Max Holloway",
    });
    expect(parse("#/fighters/Jos%C3%A9%20Aldo").param).toBe("José Aldo");
  });

  test("params may contain slashes (event urls, odd names)", () => {
    expect(parse("#/picks/evt/extra").param).toBe("evt/extra");
  });

  test("malformed percent-encoding is used verbatim, not thrown", () => {
    expect(parse("#/fighters/50%").param).toBe("50%");
  });
});

describe("routeHash", () => {
  test("builds plain and parameterized hashes", () => {
    expect(routeHash("lab")).toBe("#/lab");
    expect(routeHash("picks", "evt1")).toBe("#/picks/evt1");
  });

  test("round-trips names that need encoding", () => {
    for (const name of ["Max Holloway", "José Aldo", "O'Malley / Vera"]) {
      expect(parse(routeHash("fighters", name)).param).toBe(name);
    }
  });
});
