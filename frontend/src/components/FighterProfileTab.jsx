import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  Loader,
  Paper,
  ScrollArea,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconArrowRight,
  IconChartLine,
  IconSearch,
  IconShield,
  IconSwords,
  IconUser,
} from "@tabler/icons-react";
import { getFighterInitials } from "./FighterDisplay";
import FighterEloTrendChart from "./FighterEloTrendChart";

function getProfileResultClass(result = "") {
  const normalized = String(result).toLowerCase();

  if (normalized === "win") {
    return "win";
  }

  if (normalized === "loss") {
    return "loss";
  }

  return "other";
}

function getResultBadgeColor(result = "") {
  const resultClass = getProfileResultClass(result);

  if (resultClass === "win") {
    return "green";
  }

  if (resultClass === "loss") {
    return "red";
  }

  return "gray";
}

function getMethodSummaryTotal(summary = {}) {
  return Object.values(summary).reduce((total, value) => total + Number(value || 0), 0);
}

function formatStatLabel(value = "") {
  const labels = {
    prior_elo: "Elo",
    prior_peak_elo: "Peak Elo",
    prior_win_rate: "Win rate",
    recent_5_win_rate: "Recent 5 win rate",
    prior_finish_win_rate: "Finish win rate",
    prior_finish_loss_rate: "Finish loss rate",
    prior_fights: "UFC fights",
    prior_wins: "UFC wins",
    prior_losses: "UFC losses",

    avg_sig_str_differential_per_15: "Sig. strike diff / 15",
    avg_sig_str_landed_per_15: "Sig. strikes landed / 15",
    avg_sig_str_absorbed_per_15: "Sig. strikes absorbed / 15",
    avg_sig_str_accuracy: "Sig. strike accuracy",
    avg_sig_str_defense: "Sig. strike defense",
    avg_kd_for: "Knockdowns for",
    avg_kd_against: "Knockdowns against",

    avg_td_landed_per_15: "Takedowns landed / 15",
    avg_td_attempted_per_15: "Takedowns attempted / 15",
    avg_td_accuracy: "Takedown accuracy",
    avg_td_defense: "Takedown defense",
    avg_td_absorbed_per_15: "Takedowns absorbed / 15",
    avg_ctrl_seconds_per_15: "Control seconds / 15",
    avg_ctrl_absorbed_seconds_per_15: "Control absorbed / 15",
    avg_sub_att_per_15: "Sub attempts / 15",

    height_inches: "Height",
    reach_inches: "Reach",
    reach_minus_height_inches: "Reach minus height",
    age_years: "Age",
  };

  return labels[value] ?? value.replaceAll("_", " ");
}

function ProfileMetric({ label, value }) {
  return (
    <Paper withBorder radius="lg" p="md" className="mantine-profile-metric">
      <Text size="xs" c="dimmed" fw={800} tt="uppercase" lh={1.2}>
        {label}
      </Text>
      <Text fw={900} size="xl" mt={6} lh={1.1}>
        {value || "N/A"}
      </Text>
    </Paper>
  );
}

function ProfileSection({ title, description, children, icon }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="xl" className="mantine-profile-section">
      <Group justify="space-between" align="flex-start" mb="md">
        <div>
          <Group gap="xs" mb={4}>
            {icon}
            <Title order={2}>{title}</Title>
          </Group>
          {description && (
            <Text c="dimmed" size="sm" maw={760}>
              {description}
            </Text>
          )}
        </div>
      </Group>
      {children}
    </Card>
  );
}

export default function FighterProfileTab({
  profileFighter,
  setProfileFighter,
  profileSearchResults,
  setProfileSearchResults,
  fighterProfile,
  fighterProfileLoading,
  fighterProfileError,
  searchFighters,
  loadFighterProfile,
  setFighterA,
  setFighterB,
  setActiveView,
}) {
  const image = fighterProfile?.image ?? {};
  const headline = fighterProfile?.headline_stats ?? {};
  const styleProfile = fighterProfile?.style_profile ?? {};
  const methodSummary = fighterProfile?.method_summary ?? {};
  const profileImageUrl = image.fighter_image_url || image.image_url || "";
  const profileInitials =
    image.fighter_initials ||
    image.initials ||
    getFighterInitials(fighterProfile?.fighter || profileFighter);

  return (
    <section className="mantine-profile-layout">
      <Paper
        withBorder
        radius="xl"
        shadow="sm"
        p="xl"
        className="mantine-profile-search-card"
      >
        <Stack gap="md">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
              Fighter profile
            </Text>
            <Title order={2} mt={4}>
              Scout a fighter
            </Title>
            <Text c="dimmed" size="sm" mt="xs" lh={1.55}>
              Search a fighter to view model stats, style assumptions, notable rankings,
              method tendencies, and recent UFC fight history.
            </Text>
          </div>

          <TextInput
            label="Fighter"
            placeholder="Example: Khamzat Chimaev"
            value={profileFighter}
            leftSection={<IconSearch size={16} />}
            onChange={(event) => {
              setProfileFighter(event.target.value);
              searchFighters(event.target.value, setProfileSearchResults);
            }}
          />

          {profileSearchResults.length > 0 && (
            <Paper withBorder radius="lg" p="xs" className="mantine-search-suggestions">
              <Stack gap={6}>
                {profileSearchResults.map((name) => (
                  <Button
                    key={name}
                    variant="subtle"
                    color="gray"
                    justify="flex-start"
                    fullWidth
                    leftSection={<IconUser size={16} />}
                    onClick={() => {
                      setProfileFighter(name);
                      setProfileSearchResults([]);
                      loadFighterProfile(name);
                    }}
                  >
                    {name}
                  </Button>
                ))}
              </Stack>
            </Paper>
          )}

          <Button
            fullWidth
            size="md"
            radius="lg"
            leftSection={fighterProfileLoading ? <Loader size={16} color="white" /> : <IconSearch size={17} />}
            disabled={fighterProfileLoading || !profileFighter.trim()}
            onClick={() => loadFighterProfile(profileFighter)}
          >
            {fighterProfileLoading ? "Loading profile..." : "Load profile"}
          </Button>

          {fighterProfileError && (
            <Alert color="red" variant="light" radius="lg">
              {fighterProfileError}
            </Alert>
          )}

          {fighterProfile && (
            <>
              <Divider />
              <SimpleGrid cols={1} spacing="xs">
                <Button
                  variant="light"
                  radius="lg"
                  rightSection={<IconArrowRight size={16} />}
                  onClick={() => {
                    setFighterA(fighterProfile.fighter);
                    setActiveView("single");
                  }}
                >
                  Use as Fighter A
                </Button>

                <Button
                  variant="light"
                  radius="lg"
                  rightSection={<IconArrowRight size={16} />}
                  onClick={() => {
                    setFighterB(fighterProfile.fighter);
                    setActiveView("single");
                  }}
                >
                  Use as Fighter B
                </Button>
              </SimpleGrid>
            </>
          )}
        </Stack>
      </Paper>

      <section className="mantine-profile-panel">
        {!fighterProfile && !fighterProfileLoading && (
          <Paper withBorder radius="xl" p="xl" ta="center" className="mantine-empty-panel">
            <IconUser size={42} />
            <Title order={2} mt="sm">
              No fighter selected
            </Title>
            <Text c="dimmed" mt="xs">
              Search for a fighter to open their profile.
            </Text>
          </Paper>
        )}

        {fighterProfileLoading && (
          <Paper withBorder radius="xl" p="xl" ta="center" className="mantine-empty-panel">
            <Loader size="lg" />
            <Title order={2} mt="md">
              Loading fighter profile...
            </Title>
            <Text c="dimmed" mt="xs">
              Pulling current stats, rankings, and fight history.
            </Text>
          </Paper>
        )}

        {fighterProfile && (
          <Stack gap="lg">
            <Paper radius="xl" p="xl" className="mantine-profile-hero">
              <Group gap="xl" align="center" wrap="nowrap" className="mantine-profile-hero-content">
                <Avatar
                  src={profileImageUrl || null}
                  alt={`${fighterProfile.fighter} headshot`}
                  size={132}
                  radius={999}
                  className="mantine-profile-avatar"
                >
                  {profileInitials}
                </Avatar>

                <div className="mantine-profile-hero-copy">
                  <Badge variant="light" color="blue" size="lg" radius="xl">
                    {fighterProfile.weight_class || "Weight class unknown"}
                  </Badge>

                  <Title order={1} mt="sm" className="mantine-profile-title">
                    {fighterProfile.fighter}
                  </Title>

                  <Group gap="xs" mt="md">
                    <Badge color="indigo" variant="filled" radius="xl">
                      {styleProfile.style_label || "Style unknown"}
                    </Badge>
                    {styleProfile.tags?.slice(0, 4).map((tag) => (
                      <Badge key={tag} color="gray" variant="light" radius="xl">
                        {tag}
                      </Badge>
                    ))}
                  </Group>

                  {styleProfile.note && (
                    <Text mt="md" c="var(--mantine-color-gray-2)" maw={760} lh={1.55}>
                      {styleProfile.note}
                    </Text>
                  )}
                </div>
              </Group>
            </Paper>

            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
              <ProfileMetric label="Elo" value={headline.elo_formatted} />
              <ProfileMetric label="Peak Elo" value={headline.peak_elo_formatted} />
              <ProfileMetric
                label="UFC record"
                value={`${headline.ufc_wins ?? "?"}-${headline.ufc_losses ?? "?"}`}
              />
              <ProfileMetric label="Win rate" value={headline.win_rate_formatted} />
              <ProfileMetric label="Age" value={headline.age_formatted} />
              <ProfileMetric
                label="Height / Reach"
                value={`${headline.height || "N/A"} / ${headline.reach || "N/A"}`}
              />
            </SimpleGrid>

            <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
              <ProfileSection title="Recent form" icon={<IconChartLine size={18} />}>
                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
                  <ProfileMetric
                    label="Last 5 record"
                    value={fighterProfile.form_summary?.last_5_record}
                  />
                  <ProfileMetric
                    label="Current streak"
                    value={fighterProfile.form_summary?.current_streak}
                  />
                  <ProfileMetric
                    label="Recent results"
                    value={
                      fighterProfile.form_summary?.recent_results?.length
                        ? fighterProfile.form_summary.recent_results
                            .map((result) => result?.[0]?.toUpperCase() || "?")
                            .join(" - ")
                        : "N/A"
                    }
                  />
                </SimpleGrid>
              </ProfileSection>

              <ProfileSection title="Style profile" icon={<IconSwords size={18} />}>
                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
                  <ProfileMetric label="Striking" value={styleProfile.score_percentages?.striking} />
                  <ProfileMetric label="Grappling" value={styleProfile.score_percentages?.grappling} />
                  <ProfileMetric label="Defense" value={styleProfile.score_percentages?.defense} />
                </SimpleGrid>

                <Group gap="xs" mt="md">
                  {styleProfile.tags?.map((tag) => (
                    <Badge key={tag} color="blue" variant="light" radius="xl">
                      {tag}
                    </Badge>
                  ))}
                </Group>
              </ProfileSection>
            </SimpleGrid>

            <ProfileSection
              title="Elo / form trend"
              description="This chart shows the fighter's Elo, giving a quick view of trajectory."
              icon={<IconChartLine size={18} />}
            >
              <FighterEloTrendChart eloHistory={fighterProfile.elo_history || []} />
            </ProfileSection>

            <ProfileSection title="Notable rankings" icon={<IconShield size={18} />}>
              {fighterProfile.notable_rankings?.length === 0 && (
                <Text c="dimmed">
                  No top-10 overall or weight-class rankings found among qualified fighters.
                </Text>
              )}

              <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                {fighterProfile.notable_rankings?.map((ranking) => (
                  <Card
                    withBorder
                    radius="lg"
                    p="md"
                    key={`${ranking.metric}-${ranking.scope}-${ranking.scope_label}`}
                    className="mantine-ranking-card"
                  >
                    <Text size="xs" c="blue" fw={900} tt="uppercase">
                      {ranking.category}
                    </Text>
                    <Title order={2} mt={6}>
                      #{ranking.rank}
                    </Title>
                    <Text c="dimmed" size="sm" mt={4} lh={1.45}>
                      {ranking.description}
                    </Text>
                    <Text fw={800} size="sm" mt="xs">
                      {ranking.formatted_value}
                    </Text>
                  </Card>
                ))}
              </SimpleGrid>
            </ProfileSection>

            <ProfileSection title="Method tendencies" icon={<IconSwords size={18} />}>
              <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
                {["wins", "losses", "all"].map((bucket) => {
                  const summary = methodSummary[bucket] || {};
                  const total = getMethodSummaryTotal(summary);

                  return (
                    <Paper withBorder radius="lg" p="md" key={bucket}>
                      <Title order={3} tt="capitalize" mb="sm">
                        {bucket === "all" ? "All fights" : bucket}
                      </Title>

                      {total === 0 && <Text c="dimmed">No data</Text>}

                      <Stack gap={8}>
                        {Object.entries(summary).map(([method, count]) => (
                          <Group justify="space-between" key={`${bucket}-${method}`}>
                            <Text c="dimmed" size="sm">
                              {method}
                            </Text>
                            <Text fw={900}>{count}</Text>
                          </Group>
                        ))}
                      </Stack>
                    </Paper>
                  );
                })}
              </SimpleGrid>
            </ProfileSection>

            <ProfileSection title="Stat snapshot" icon={<IconShield size={18} />}>
              <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="sm">
                {fighterProfile.profile_stats?.map((stat) => (
                  <ProfileMetric
                    key={stat.key}
                    label={formatStatLabel(stat.key)}
                    value={stat.formatted_value}
                  />
                ))}
              </SimpleGrid>
            </ProfileSection>

            <ProfileSection title="Recent fight history" icon={<IconSwords size={18} />}>
              <ScrollArea.Autosize mah={620} type="auto">
                <Stack gap="sm">
                  {fighterProfile.recent_fights?.map((fight) => (
                    <Paper
                      withBorder
                      radius="lg"
                      p="md"
                      key={fight.fight_url}
                      className="mantine-profile-fight-row"
                    >
                      <Group justify="space-between" align="center" gap="md" wrap="nowrap">
                        <div>
                          <Button
                            variant="subtle"
                            color="gray"
                            px={0}
                            className="mantine-profile-opponent-button"
                            onClick={() => {
                              setProfileFighter(fight.opponent);
                              loadFighterProfile(fight.opponent);
                              window.scrollTo({ top: 0, behavior: "smooth" });
                            }}
                          >
                            {fight.opponent || "Unknown opponent"}
                          </Button>

                          <Text c="dimmed" size="sm" mt={2}>
                            {fight.event_date} • {fight.weight_class} • {fight.event_name}
                          </Text>
                        </div>

                        <Badge
                          color={getResultBadgeColor(fight.result)}
                          variant="light"
                          size="lg"
                          radius="lg"
                          className="mantine-profile-result-badge"
                        >
                          {fight.result || "N/A"}
                          {fight.method_category ? ` • ${fight.method_category}` : ""}
                          {fight.round ? ` • R${fight.round}` : ""}
                          {fight.time ? ` • ${fight.time}` : ""}
                        </Badge>
                      </Group>
                    </Paper>
                  ))}
                </Stack>
              </ScrollArea.Autosize>
            </ProfileSection>
          </Stack>
        )}
      </section>
    </section>
  );
}
