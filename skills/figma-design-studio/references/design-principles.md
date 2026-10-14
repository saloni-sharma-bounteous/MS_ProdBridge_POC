# Design principles and craft reference

## Contents
1. Mindset
2. Visual craft rules
3. Scales and sizes
4. Colour
5. Components and patterns
6. States, content and motion
7. Accessibility
8. Other platforms
9. Review checklist

## 1. Mindset

- **Clarity**: one primary action per screen. If everything is emphasised, nothing is.
- **Deference**: the interface frames the content and gets out of the way. Chrome is quiet, content is loud.
- **Depth**: use layers, blur and subtle shadow to show what sits above what. Not decoration.
- **Restraint**: fewer colours, fewer weights, fewer borders. Space and alignment do the work that boxes and lines do in weaker designs.
- **Craft is in the details**: optical alignment, consistent radii, correct line height, real data, careful empty states.
- Design the **whole journey**, including first run, errors and the moment of success.

## 2. Visual craft rules

1. **Hierarchy by size, weight and contrast**, in that order. Aim for 3 text levels per screen: title, body, secondary.
2. **Align to a grid.** 4 pt base, 8 pt rhythm. Screen margins 16 pt (20 for large titles). Group related items closer than unrelated ones (proximity beats borders).
3. **One accent colour** for interactive things and key emphasis. Status colours (green, amber, red) only for status, always with a label or icon too.
4. **Neutrals do most of the work.** Use 3 surface levels (background, surface, raised) rather than many hues.
5. **Corner radii form a family**: 8 small, 12 controls, 20 cards, 28 sheets, device corners match the hardware. Nested radii = outer radius minus padding.
6. **Shadows are soft and layered**, low opacity, large blur, tiny offset. Never a hard grey drop shadow. In dark mode, rely on surface lightness, not shadow.
7. **Materials**: translucent bars (tab bar, nav bar, action bar) use backdrop blur with saturation so content shows through softly.
8. **Typography**: tight tracking on large text, slightly loose on small caps labels. Max two weights per screen in practice (regular/medium and semibold/bold). Left-align body text.
9. **Numbers are heroes** in data apps: large, bold, with a small quiet unit or label beside them. Use tabular figures for columns.
10. **Icons**: one stroke weight (1.75-2 at 24 px), consistent corner style, optically centred, same size family. Pair with labels in navigation.
11. **Imagery and illustration**: if you use gradients, keep them analogous (neighbouring hues), soft and low contrast, and use them once, not everywhere.
12. **Whitespace is a feature.** If a screen feels busy, remove something before you shrink anything.
13. **Avoid the template look**: no default purple-to-blue gradients, no heavy borders on every card, no centered-everything layouts, no stock-looking icon mixes, no five font sizes within one card.

## 3. Scales and sizes

### Type scale (iOS, points)

| Style | Size / line | Weight |
|---|---|---|
| Large title | 34 / 41 | Bold |
| Title 1 | 28 / 34 | Bold |
| Title 2 | 22 / 28 | Bold |
| Title 3 | 20 / 25 | Semibold |
| Headline | 17 / 22 | Semibold |
| Body | 17 / 22 | Regular |
| Callout | 16 / 21 | Regular |
| Subhead | 15 / 20 | Regular |
| Footnote | 13 / 18 | Regular |
| Caption | 12 / 16 | Regular |

Fonts: SF Pro is the target. Inter is the open fallback. On web use the system stack.

### Spacing and sizing

- Spacing tokens: 4, 8, 12, 16, 20, 24, 32, 40, 48.
- Minimum touch target: **44 x 44 pt**. Primary button height 50. Row height 44 minimum, 60 for rich rows.
- Radii: 8, 12, 20, 28.

### iPhone frame (default)

- iPhone 16: **393 x 852**. iPhone 16 Pro: 402 x 874. iPhone SE: 375 x 667.
- Status bar area about 54, home indicator area 34, nav bar 44, large title area about 96, tab bar 49 plus 34 safe area (about 83-88 on screen).
- Keep primary actions in the thumb zone (lower third). Put a sticky action bar above the home indicator.

## 4. Colour

- Define semantic tokens, not raw hex in components: `bg`, `surface`, `label`, `label-2`, `label-3`, `sep`, `accent`, `good`, `warn`, `bad`, each with a tint for backgrounds.
- Build the dark theme as its own set, not an inversion: lift the surface slightly, desaturate and brighten the accent, reduce shadows.
- Contrast: body text 4.5:1 or better, large text and UI components 3:1 or better. `label-3` is for non-essential hints only.
- Pick the accent with intent. Examples: trust and finance (deep teal, ink blue), health (soft green), creative (warm coral), security (indigo with high contrast). Test it in both themes.

## 5. Components and patterns

Use the components in `assets/design-system.css`: navbar and large title, tab bar, action bar, search, segmented control, inset-grouped list and rows, cards, stat tiles, chips, meter, check, buttons (primary, tinted, plain), switch, avatar, hero.

Patterns to prefer:

- **Inset grouped lists** for settings and details. **Cards** for summaries with a main number.
- **Segmented controls** for 2-4 filters of the same list. **Tab bar** for 3-5 top-level areas only.
- **Sheets** for focused tasks that return to the same place. **Push navigation** for drilling into detail.
- **Primary action** pinned at the bottom for forms and decisions. Destructive actions need a clear label and confirmation, never red by default on the main button.
- **Progressive disclosure**: show the essentials, put the rest one tap away.

## 6. States, content and motion

- Every screen with data needs: **loading** (skeletons, not spinners, when layout is known), **empty** (say what this is, why it is empty, and the next action), **error** (what happened, what to do, retry), and **success** (a quiet confirmation).
- Copy: short, specific, human. Buttons are verbs ("Approve", "Send invite"). Errors never blame the user.
- Use believable data: varied name lengths, long values that wrap, zero and large numbers.
- Motion notes: 200-350 ms, ease-out for entering, ease-in for leaving, springs for direct manipulation. Respect Reduce Motion by crossfading instead of moving.

## 7. Accessibility

- Support Dynamic Type: layouts must survive text two sizes larger. Do not fix heights on text containers.
- Never convey meaning with colour alone: pair status colour with a label or icon.
- Provide clear focus order, labels for icon-only buttons, and 44 pt targets.
- Check both themes for contrast.

## 8. Other platforms

| Platform | Frame | Notes |
|---|---|---|
| iPad | 834 x 1194 (11") | Sidebar plus content, two or three columns, larger margins (24-32) |
| Mac window | 1440 x 900 | Sidebar 240, toolbar 52, denser rows (28-32), hover and keyboard states |
| Web desktop | 1440 wide, 12-col grid, 80 margins | Max content width 1200, 8 pt rhythm |
| Web tablet / mobile | 768 / 390 | Stack columns, 16-24 margins |
| Android | 412 x 915 | Material conventions: top app bar, bottom nav, FAB. Respect platform patterns |

When the platform is not iPhone, adapt `.device` width and height in the board CSS and keep the same tokens.

## 9. Review checklist (use in the critique loop)

Answer each honestly while looking at the rendered image.

1. **Squint test**: with eyes half closed, is the most important thing obvious?
2. **One primary action** per screen, clearly the strongest element?
3. **Alignment**: do left edges, baselines and gaps line up on the 4/8 grid?
4. **Spacing**: are related items grouped and unrelated items separated? Any cramped or floating elements?
5. **Type**: no more than 3 sizes in a card, line lengths comfortable, nothing truncated unintentionally?
6. **Colour**: accent used only for interaction and emphasis? Status never colour-only? Both themes readable?
7. **Consistency**: same radii, icon weight, row height and button style across screens?
8. **Polish**: consistent shadows, no stray borders, icons optically centred, safe areas respected?
9. **Content**: real, varied, believable? States covered?
10. **Taste**: does it look designed, or like a template? What is the one memorable detail?

Name the 5 weakest items, fix them, and re-check.
