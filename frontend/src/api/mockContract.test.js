/**
 * Mock-contract check (W8). The mock API drifted from the real one several
 * times (missing fields, missing functions) and each drift surfaced as a
 * broken demo. Two guards:
 *
 * 1. Every `mock.<fn>` the client dispatches to in mock mode must exist.
 * 2. Key mock responses must carry the fields the UI reads — and must NEVER
 *    carry an email (the same invariant the backend enforces).
 */
import { describe, expect, test } from "vitest";
import * as mock from "./mock.js";
// Vite raw import: the client source, for statically extracting mock.* refs.
import clientSource from "./client.js?raw";

describe("client -> mock dispatch", () => {
  test("every mock.* reference in client.js is an exported mock function", () => {
    const referenced = [...clientSource.matchAll(/\bmock\.([A-Za-z_$][\w$]*)\s*\(/g)]
      .map((match) => match[1]);
    expect(referenced.length).toBeGreaterThan(20);
    const missing = [...new Set(referenced)].filter(
      (name) => typeof mock[name] !== "function"
    );
    expect(missing).toEqual([]);
  });
});

function expectNoEmail(row) {
  expect(row).not.toHaveProperty("email");
  const name = row.display_name ?? row.name ?? "";
  expect(String(name)).not.toContain("@");
}

describe("mock response shapes carry what the UI reads", () => {
  test("user leaderboard rows", async () => {
    const rows = await mock.getUserLeaderboard();
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      for (const key of [
        "rank",
        "user_id",
        "display_name",
        "rating",
        "wins",
        "losses",
        "graded",
        "accuracy",
        "is_me",
        "provisional",
      ]) {
        expect(row, `leaderboard row missing '${key}'`).toHaveProperty(key);
      }
      expectNoEmail(row);
    }
  });

  test("card leaderboard rows", async () => {
    const rows = await mock.getUserCardLeaderboard("mock-card-1");
    for (const row of rows) {
      expect(row).toHaveProperty("user_id");
      expect(row).toHaveProperty("display_name");
      expectNoEmail(row);
    }
  });

  test("friends overview", async () => {
    const overview = await mock.getFriends();
    for (const key of ["friends", "incoming", "outgoing"]) {
      expect(Array.isArray(overview[key]), `overview.${key} is an array`).toBe(true);
    }
    for (const row of [...overview.friends, ...overview.incoming, ...overview.outgoing]) {
      expect(row).toHaveProperty("friendship_id");
      expect(row).toHaveProperty("user_id");
      expect(row).toHaveProperty("display_name");
      expectNoEmail(row);
    }
  });

  test("future cards and my predictions", async () => {
    const cards = await mock.getFutureCards();
    expect(cards.length).toBeGreaterThan(0);
    for (const card of cards) {
      expect(card).toHaveProperty("event_id");
      expect(card).toHaveProperty("event_name");
      expect(card).toHaveProperty("event_date");
    }

    const picks = await mock.listPredictions();
    for (const pick of picks) {
      expect(pick).toHaveProperty("fight_url");
      expect(pick).toHaveProperty("picked_fighter");
      expect(pick).toHaveProperty("status");
    }
  });

  test("card predictions include fighters and model probabilities", async () => {
    const cards = await mock.getFutureCards();
    const detail = await mock.getFutureCardPredictions(cards[0].event_id);
    expect(detail).toHaveProperty("event_name");
    expect(detail.fights.length).toBeGreaterThan(0);
    for (const fight of detail.fights) {
      expect(fight).toHaveProperty("fighter_1");
      expect(fight).toHaveProperty("fighter_2");
      expect(fight).toHaveProperty("fight_url");
    }
  });
});
