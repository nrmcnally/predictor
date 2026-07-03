import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { LeaderboardRow } from "./LeaderboardRow.jsx";

test("renders rank, identity, score, and stats cells", () => {
  const { container } = render(
    <LeaderboardRow
      rank={1}
      isMe
      scoreLabel="FIGHT IQ"
      scoreValue={1042}
      leading={<span>Ada</span>}
      stats={<span>Accuracy: 71%</span>}
    />
  );

  expect(screen.getByText("#1")).toBeInTheDocument();
  expect(screen.getByText("Ada")).toBeInTheDocument();
  expect(screen.getByText("FIGHT IQ")).toBeInTheDocument();
  expect(screen.getByText("1042")).toBeInTheDocument();
  expect(screen.getByText("Accuracy: 71%")).toBeInTheDocument();

  const row = container.querySelector(".leaderboard-row");
  expect(row.className).toContain("podium-1");
  expect(row.className).toContain("is-me");
});

test("no podium styling past third place, no is-me for others", () => {
  const { container } = render(
    <LeaderboardRow rank={7} scoreLabel="Elo" scoreValue={900} leading="Boz" />
  );
  const row = container.querySelector(".leaderboard-row");
  expect(row.className).not.toContain("podium");
  expect(row.className).not.toContain("is-me");
});
