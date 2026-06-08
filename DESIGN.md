---
name: Xingtu Short Video BI
description: Light enterprise BI dashboard for Xingtu short video operations.
colors:
  ink: "#172033"
  ink-strong: "#10233c"
  text-muted: "#65748a"
  text-subtle: "#7890aa"
  app-bg: "#f5f7fb"
  surface: "#ffffff"
  surface-muted: "#f7f9fc"
  panel-tint: "#f3f7fb"
  border: "#dde6f1"
  border-soft: "#edf1f6"
  primary: "#147bb7"
  primary-strong: "#0d5b8e"
  primary-soft: "#eef8fd"
  success: "#1f7153"
  success-soft: "#effbf6"
  warning: "#996312"
  warning-soft: "#fff8eb"
typography:
  headline:
    fontFamily: "PingFang SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0"
  title:
    fontFamily: "PingFang SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0"
  body:
    fontFamily: "PingFang SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: "0"
  label:
    fontFamily: "PingFang SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "0"
rounded:
  sm: "6px"
  md: "8px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "36px"
components:
  button-filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 13px"
  button-filter-active:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-strong}"
    rounded: "{rounded.md}"
    padding: "8px 13px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16px"
---

# Design System: Xingtu Short Video BI

## 1. Overview

**Creative North Star: "Operations Ledger"**

The interface should feel like a reliable operating ledger inside Feishu: quiet, structured, and ready for repeated use. It is not a public marketing page and not a dark data wall. Its job is to let operators and leaders scan total exposure, publishing volume, completion-rate availability, actor contribution, and single-video extremes without decoding technical metadata.

The design rejects decorative BI tropes: dark dashboards, saturated gradients, nested cards, and technical explanation blocks. Density is acceptable when it helps comparison, but each section needs a clear task: overview, video ranking, account performance, actor performance, or data maintenance.

**Key Characteristics:**

- Light enterprise dashboard, not dark screen.
- Restrained blue accent for navigation, selected state, chart emphasis, and primary action.
- Flat containers with thin borders instead of soft decorative shadows.
- Business copy only; no source-field or fallback explanations in the report body.
- Responsive structure suitable for Feishu iframe widths.

## 2. Colors

The palette is cool, restrained, and operational: blue is used as a state and emphasis color, while most surfaces remain white or pale blue-gray.

### Primary

- **Operational Blue** (#147bb7): primary action, active navigation, chart bars, and small emphasis icons.
- **Deep BI Blue** (#0d5b8e): hover and selected text where the primary needs stronger contrast.
- **Selection Blue Tint** (#eef8fd): selected tab and active filter background.

### Neutral

- **Dashboard Canvas** (#f5f7fb): page background and sticky navigation backing.
- **Panel Surface** (#ffffff): KPI cards, ranking cards, charts, tables, and admin panel.
- **Panel Tint** (#f3f7fb): table header and low-emphasis grouped surfaces.
- **Business Ink** (#172033): default text.
- **Metric Ink** (#10233c): KPI and ranking numeric values.
- **Muted Text** (#65748a): descriptions and secondary labels.
- **Subtle Text** (#7890aa): table metadata and definition-list labels.
- **Panel Border** (#dde6f1): primary container border.
- **Divider Border** (#edf1f6): table row and low-emphasis dividers.

### State

- **Verified Green** (#1f7153 / #effbf6): refreshed or successful state.
- **Review Amber** (#996312 / #fff8eb): warning or sample-data state.

### Named Rules

**The One Accent Rule.** Blue is the only dominant accent on the report surface; green and amber are reserved for state.

**The No Decoration Rule.** Do not add gradient text, glass panels, or ornamental shadows to make the dashboard feel more "BI".

## 3. Typography

**Display Font:** PingFang SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif
**Body Font:** PingFang SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif
**Label/Mono Font:** Same family; no separate display or mono family.

**Character:** Familiar Chinese enterprise UI typography. The hierarchy should come from weight, size, spacing, and table structure, not decorative font choices.

### Hierarchy

- **Headline** (700, 28px, 1.2): page-level dashboard title and admin primary title.
- **Title** (700, 22px, 1.3): major report sections.
- **Panel Title** (700, 16px, 1.3): chart and card titles.
- **Body** (400, 14px, 1.7): descriptions, helper copy, and table content.
- **Label** (700, 12-13px, 1.4): KPI labels, tags, table headers, and metadata labels.

### Named Rules

**The Product Scale Rule.** Do not use fluid hero typography or oversized marketing headings. This dashboard is a working surface.

## 4. Elevation

The system uses tonal layering and 1px borders, not decorative shadows. Depth is created through background contrast, table headers, sticky navigation, and consistent borders. Shadows should appear only if a future floating layer needs stateful separation, such as a dropdown or tooltip.

### Named Rules

**The Flat-By-Default Rule.** Panels are flat at rest. Avoid pairing a 1px border with wide soft shadows on the same element.

## 5. Components

### Buttons

- **Shape:** compact rectangle with 8px radius.
- **Primary:** Operational Blue background with white text for admin upload.
- **Filter:** white background, border, muted text; selected state uses Selection Blue Tint and Deep BI Blue.
- **Hover / Focus:** border and text shift toward primary; focus must be visible with an outline or ring.

### Chips

- **Style:** pill badge only for status such as refreshed, sample data, warning, or verified state.
- **State:** do not use badges as decorative labels across every section.

### Cards / Containers

- **Corner Style:** 8px radius.
- **Background:** white panel surface.
- **Shadow Strategy:** no default shadow.
- **Border:** 1px Panel Border.
- **Internal Padding:** 14-20px depending on density.

### Inputs / Fields

- **Style:** 1px border, white background, 8px radius.
- **Focus:** visible border or outline in primary blue.
- **Error / Disabled:** error text should be explicit and remain readable; disabled upload button can reduce opacity but must keep its label legible.

### Navigation

- **Style:** sticky tab row with compact buttons.
- **Behavior:** wraps on narrow iframe widths, never forces the page itself to scroll horizontally.

### Tables

- **Style:** dense but readable, with tinted header, 13px cell text, and row dividers.
- **Behavior:** table container may scroll horizontally; the whole page should not.
- **Data:** exposure values above five digits use 万, and missing 5S values remain 未提供.

## 6. Do's and Don'ts

Do:

- Keep the dashboard light, restrained, and business-first.
- Put KPI summary and Top1/Bot1 ranking above long tables.
- Use consistent numeric formatting across cards, charts, and tables.
- Preserve confirmed business口径 even when data looks sparse.
- Test desktop, tablet, mobile, and Feishu iframe-like widths.

Don't:

- Do not add dark-mode big-screen styling.
- Do not show sheet names, source fields, fallback logic, or missing-field explanations on the report body.
- Do not use gradient text, glassmorphism, side-stripe card accents, or nested cards.
- Do not make chart labels overflow or hide critical video titles without useful context.
- Do not replace missing 5S completion data with ordinary completion-rate fields.
