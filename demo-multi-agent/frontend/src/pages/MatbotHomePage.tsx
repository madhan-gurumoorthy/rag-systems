/**
 * Matbot multi-agents — landing page.
 *
 * A single-screen explainer for the `matbot-multi-agents` platform.
 * Sections, in order:
 *   1. Top bar — product wordmark on the left, color-mode toggle on
 *      the right. Renders the visible page heading (`<h2>`), since
 *      <Page> owns the (visually hidden) `<h1>`.
 *   2. Hero — one-sentence value prop + supporting paragraph.
 *   3. Features — three cards describing what the substrate provides.
 *   4. Packs — the active SOP packs hosted by the platform.
 *   5. Footer — minimal attribution + repo + health endpoints.
 *
 * All visible text is static. The page does not call any backend
 * endpoints — it is a marketing surface served by the same FastAPI
 * process that hosts the agent A2A API. If the page needs dynamic
 * content later (e.g. a "live pack list" fed by `/api/packs`), wire
 * it through fetch + useEffect; do not invent new state machinery.
 */

import * as React from "react";

import { Container } from "../components/ld/Container";
import { Grid, GridColumn } from "../components/ld/Grid";
import { Card, CardHeader, CardContent } from "../components/ld/Card";
import { Heading, Body, Caption } from "../components/ld/Text";
import { Switch } from "../components/ld/Switch";
import { SpotIcon } from "../components/ld/SpotIcon";
import { Icon } from "../components/ld/Icons";
import { Link } from "../components/ld/Link";
import { Tag } from "../components/ld/Tag";
import { Divider } from "../components/ld/Divider";
import { VisuallyHidden } from "../components/ld/VisuallyHidden";
import { useColorMode } from "../utils/ColorMode";

// ── Static content ──────────────────────────────────────────────

type Feature = {
  iconName: string;
  title: string;
  description: string;
};

const FEATURES: Feature[] = [
  {
    iconName: "Flash",
    title: "Pack-driven SOPs",
    description:
      "Each problem domain ships as a self-contained pack — prompts, tools, decision matrix, and closure templates live together. The framework stays generic.",
  },
  {
    iconName: "Gear",
    title: "Generic substrate",
    description:
      "Triage, diagnostic, decision, action, and closure nodes are reused across every pack. Domain knowledge enters through config, never through framework branches.",
  },
  {
    iconName: "CheckCircle",
    title: "Human-in-the-loop",
    description:
      "High-risk actions gate through approval. Decisions, evidence, and side-channel state persist in four canonical tables — auditable end-to-end.",
  },
];

type Pack = {
  id: string;
  name: string;
  owner: string;
  description: string;
  status: "production" | "toy";
};

const PACKS: Pack[] = [
  {
    id: "gif_tote_validation",
    name: "GIF Tote Validation",
    owner: "MerchantOps · Item Setup/Maintenance",
    description:
      "Autonomous validation and resolution of GIF Tote ServiceNow incidents — dimension extraction, API validation, decision routing, and ticket updates.",
    status: "production",
  },
  {
    id: "devops_health_check",
    name: "DevOps Health Check",
    owner: "DevOps · Platform",
    description:
      "Minimal reference pack exercising the substrate end-to-end with no external dependencies. Pings a host, checks CPU, closes HEALTHY or proposes a restart.",
    status: "toy",
  },
];

// ── Page ────────────────────────────────────────────────────────

export function MatbotHomePage(): JSX.Element {
  const { mode, toggle } = useColorMode();
  const isDark = mode === "dark";

  return (
    <Container>
      {/* ── Top bar: visible h2 + color-mode toggle ────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          paddingTop: 24,
          paddingBottom: 24,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <SpotIcon color="brand" size="large">
            <Icon name="Magic" decorative />
          </SpotIcon>
          <Heading as="h2" size="medium">
            matbot multi-agents
          </Heading>
        </div>

        {/* Switch labels itself; the visible "Dark mode" text is the
            switch's own label and is read by screen readers. */}
        <Switch
          label={isDark ? "Dark mode" : "Light mode"}
          isOn={isDark}
          onClick={toggle}
        />
      </header>

      {/* ── Hero ────────────────────────────────────────────────── */}
      <section
        aria-labelledby="hero-heading"
        style={{ marginBottom: 48, marginTop: 16 }}
      >
        <Grid hasGutter>
          <GridColumn sm={12} md={12} lg={8} xl={8}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <Tag color="brand" variant="primary">
                Walmart · ITEM-OPS
              </Tag>
              <Heading as="h3" id="hero-heading" size="large">
                A pack-driven agent platform for autonomous incident resolution
              </Heading>
              <Body
                as="p"
                size="large"
                style={{
                  color: "var(--ld-semantic-color-text-subtle)",
                  margin: 0,
                  maxWidth: 720,
                  lineHeight: 1.55,
                }}
              >
                matbot routes incoming work items through a triage → diagnose →
                decide → act → close pipeline. The framework is pack-agnostic;
                each domain plugs in prompts, tools, and rules without touching
                the substrate.
              </Body>
            </div>
          </GridColumn>
        </Grid>
      </section>

      <div style={{ margin: "24px 0" }}>
        <Divider />
      </div>

      {/* ── Features ────────────────────────────────────────────── */}
      <section
        aria-labelledby="features-heading"
        style={{ marginBottom: 48, marginTop: 32 }}
      >
        <Heading
          as="h3"
          id="features-heading"
          size="medium"
          style={{ marginBottom: 24 }}
        >
          What the platform provides
        </Heading>
        <Grid hasGutter>
          {FEATURES.map((feature) => (
            <GridColumn key={feature.title} sm={12} md={4} lg={4} xl={4}>
              <Card size="small">
                <CardHeader
                  leadingIcon={
                    <SpotIcon color="brand" size="small">
                      <Icon name={feature.iconName} decorative />
                    </SpotIcon>
                  }
                  title={feature.title}
                />
                <CardContent>
                  <Body
                    as="p"
                    size="medium"
                    style={{
                      margin: 0,
                      color: "var(--ld-semantic-color-text-subtle)",
                      lineHeight: 1.55,
                    }}
                  >
                    {feature.description}
                  </Body>
                </CardContent>
              </Card>
            </GridColumn>
          ))}
        </Grid>
      </section>

      <div style={{ margin: "24px 0" }}>
        <Divider />
      </div>

      {/* ── Packs ───────────────────────────────────────────────── */}
      <section
        aria-labelledby="packs-heading"
        style={{ marginBottom: 48, marginTop: 32 }}
      >
        <Heading
          as="h3"
          id="packs-heading"
          size="medium"
          style={{ marginBottom: 8 }}
        >
          Active packs
        </Heading>
        <Body
          as="p"
          size="medium"
          style={{
            color: "var(--ld-semantic-color-text-subtle)",
            margin: 0,
            marginBottom: 24,
            maxWidth: 720,
            lineHeight: 1.55,
          }}
        >
          Each pack is a self-contained SOP. The framework runs identically for
          every pack — what differs is the YAML config, prompts, and tool
          manifest.
        </Body>
        <Grid hasGutter>
          {PACKS.map((pack) => (
            <GridColumn key={pack.id} sm={12} md={6} lg={6} xl={6}>
              <Card size="small">
                <CardHeader
                  title={pack.name}
                  trailing={
                    <Tag
                      color={pack.status === "production" ? "positive" : "gray"}
                      variant="secondary"
                    >
                      {pack.status === "production" ? "Production" : "Reference"}
                    </Tag>
                  }
                />
                <CardContent>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    <Caption
                      as="p"
                      color="subtle"
                      style={{ margin: 0, fontWeight: 600 }}
                    >
                      {pack.owner}
                    </Caption>
                    <Body
                      as="p"
                      size="medium"
                      style={{
                        margin: 0,
                        color: "var(--ld-semantic-color-text-subtle)",
                        lineHeight: 1.55,
                      }}
                    >
                      {pack.description}
                    </Body>
                    <Caption
                      as="p"
                      isMonospace
                      style={{
                        margin: 0,
                        color: "var(--ld-semantic-color-text-subtlest)",
                      }}
                    >
                      packs/{pack.id}/
                    </Caption>
                  </div>
                </CardContent>
              </Card>
            </GridColumn>
          ))}
        </Grid>
      </section>

      <div style={{ margin: "24px 0" }}>
        <Divider />
      </div>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer
        aria-labelledby="footer-heading"
        style={{
          marginTop: 32,
          paddingTop: 24,
          paddingBottom: 48,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <VisuallyHidden as="h3" id="footer-heading">
          Repository and operational links
        </VisuallyHidden>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 24,
            alignItems: "center",
          }}
        >
          <Link
            href="https://gecgithub01.walmart.com/ITEM-OPS/matbot-multi-agents"
            target="_blank"
          >
            Repository
            <VisuallyHidden> (opens in new window)</VisuallyHidden>
          </Link>
          <Link href="/healthz">Health</Link>
          <Link href="/readyz">Readiness</Link>
        </div>
        <Caption
          as="p"
          color="subtlest"
          style={{ margin: 0 }}
        >
          Walmart Item Operations · matbot-multi-agents
        </Caption>
      </footer>
    </Container>
  );
}

MatbotHomePage.displayName = "MatbotHomePage";
