# Delivering into Figma

## Contents
1. Pick the route
2. Route A: Figma MCP connected (native layers)
3. Route B: HTML boards captured into Figma
4. Route C: manual import
5. `tokens.json` format
6. Connecting the Figma MCP

## 1. Pick the route

Look at your tool list. Tool names may carry a prefix such as `mcp__figma__`.

| You have | Route |
|---|---|
| A Figma tool that writes to the canvas (`use_figma`) | **A** |
| Only a capture tool (`generate_figma_design`) | **B** |
| No Figma tools | **C**, and tell the user how to connect (section 6) |

Writing to Figma files needs a **Full seat**. A Dev seat is read-only. If a write fails with a permission error, say so and fall back to Route C.

Always tell the user which route you used. Never say something is in Figma unless a tool call confirmed it.

## 2. Route A: native layers through the Figma MCP

1. If Figma provides its own skills in this session (for example `figma-use`, `figma-generate-design`, `figma-generate-library`), **read and follow them first**. They know the current Plugin API rules.
2. You need a file URL. If the user has not given one, ask for it (a blank Figma Design file is fine).
3. Build in this order, checking the result after each step:

   **Page "Foundations"**
   - Variables collection `Color` with modes **Light** and **Dark**, using the names in `tokens.json` (`bg`, `surface`, `label`, `accent`, and so on).
   - Variable collections for `Spacing` and `Radius`.
   - Text styles for each type-scale step (Large title to Caption).
   - Effect styles for the shadows.

   **Page "Components"**
   - Components with variants: Button (primary, tinted, plain), List row, Chip (good, warn, bad, neutral), Tab bar, Nav bar, Stat card, Search, Segmented control, Switch, Avatar.
   - Build each with **auto layout**, and bind fills, text colours and radii to the variables. No hard-coded hex values.

   **Page "Lo-fi"** and **Page "Hi-fi"**
   - One frame per screen at the device size, named `NN / Screen name` (use the `data-figma-name` values from the boards).
   - Screens are assembled from component instances, with auto layout and sensible constraints.
   - Light and dark versions use the Light/Dark variable modes, not duplicated colours.
   - Put frames in a row with 80-100 px gaps, flow order left to right. Add connector arrows only if the prototype tooling is available.

4. Fonts: use SF Pro if it exists in the file, otherwise Inter. Check availability before setting text, otherwise text will fail to render.
5. Verify: take a screenshot of each page or frame with the screenshot tool if one exists, compare with the board PNGs, and fix differences.
6. Layer hygiene: meaningful names, no "Frame 123", no leftover temp layers, nothing flattened that should stay editable.

Reply with the Figma file link and a list of pages and components created.

## 3. Route B: HTML boards captured into Figma

If only `generate_figma_design` (code to canvas) is available:

1. Serve the board: from `design/`, run `python -m http.server 8765`.
2. Call the capture tool on `http://localhost:8765/hifi/board.html` (and the lo-fi board), following the tool's instructions for target file and page.
3. Frame names come from the DOM, so keep `data-figma-name` and semantic class names.
4. Tell the user the result is captured layers. It is editable but not yet componentised, and recommend Route A or a clean-up pass for the design system.

## 4. Route C: manual import

Deliver `lofi.png`, `hifi.png`, both boards and `tokens.json`, and give these steps:

- **Quick look**: drag the PNGs into a Figma file.
- **Editable layers**: use the free "html.to.design" plugin on the served board URL, or export frames as SVG from the browser and drop the SVG onto the canvas.
- **Variables**: import `tokens.json` with a variables or tokens plugin (for example Tokens Studio) so the colours, type and spacing match the CSS.

Be honest that imported layers need some clean-up (auto layout, components).

## 5. `tokens.json` format

Keep this structure so a plugin or a script can read it.

```json
{
  "color": {
    "light": {
      "bg": "#F2F2F7", "surface": "#FFFFFF", "label": "#111113", "label-2": "#5E5E66",
      "label-3": "#8A8A92", "separator": "#3C3C4329", "accent": "#0A6CFF",
      "accent-tint": "#0A6CFF1F", "good": "#1B8449", "warn": "#A9610A", "bad": "#CE3328"
    },
    "dark": {
      "bg": "#000000", "surface": "#1C1C1E", "label": "#F5F5F7", "label-2": "#A6A6AE",
      "label-3": "#6F6F77", "separator": "#5454588C", "accent": "#4C9AFF",
      "accent-tint": "#4C9AFF2E", "good": "#3DD17F", "warn": "#FFB340", "bad": "#FF6B61"
    }
  },
  "type": {
    "large-title": { "size": 34, "line": 41, "weight": 700 },
    "title-1": { "size": 28, "line": 34, "weight": 700 },
    "headline": { "size": 17, "line": 22, "weight": 600 },
    "body": { "size": 17, "line": 22, "weight": 400 },
    "footnote": { "size": 13, "line": 18, "weight": 400 }
  },
  "spacing": { "1": 4, "2": 8, "3": 12, "4": 16, "5": 20, "6": 24, "8": 32, "10": 40 },
  "radius": { "sm": 8, "md": 12, "lg": 20, "xl": 28 },
  "shadow": {
    "card": "0 1px 2px rgba(16,24,40,.06)",
    "raised": "0 10px 30px rgba(16,24,40,.10)"
  }
}
```

Replace the accent values (and tints) with the product's chosen accent, and keep `tokens.json` and the CSS `:root` overrides identical.

## 6. Connecting the Figma MCP

Tell the user, only if the tools are missing:

- With the Claude Code CLI: `claude mcp add --transport http figma https://mcp.figma.com/mcp`, then run `/mcp` and authenticate with Figma.
- Without the CLI, add a `.mcp.json` file in the project folder:

```json
{
  "mcpServers": {
    "figma": { "type": "http", "url": "https://mcp.figma.com/mcp" }
  }
}
```

  Restart Claude Code, then authenticate Figma from `/mcp`.
- The user needs a Figma account with a **Full seat** to let the agent write to a file.
