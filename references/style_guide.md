# Style guide: from company to film

The film must feel like *this* company. Decide these five things from your research before writing film.json.

## 1. Brand personality → settings

| personality (examples) | palette approach | mood / theme | bpm1 | nostalgia |
|---|---|---|---|---|
| Heritage manufacturer, home appliances (美的, 海尔, 格力) | brand blue kept deep; champagne-gold accent; ivory light; obsidian dark | warm / uplift | 92–96 | yes |
| Luxury / premium (COLMO, 茅台, Hermès, Lexus) | black, warm greys, one metallic accent (gold, bronze); brand color only in the wordmark | luxury / noble | 84–90 | if heritage |
| Deep tech / AI / chips (华为, 大疆, NVIDIA) | near-black + one electric accent (brand hue), cool silver metal, deep navy | tech / bright | 96–104 | no (unless > 20 yrs) |
| Consumer internet / young brands (字节, 小米, 泡泡玛特) | brand color as the accent (it can be bold), clean light background | playful / bright | 100–104 | no |
| Energy / auto / infrastructure (比亚迪, 宁德时代, 国家电网) | deep brand tone, silver metal, a clean energy accent (green/cyan) | epic / uplift | 92–98 | yes if old |
| Finance / consulting (招商银行, 平安) | navy/deep red, gold accent, restrained | luxury / noble | 88–92 | optional |
| Food / beverage / retail (蒙牛, 星巴克, 元气森林) | warm light backgrounds, brand color accent, soft | warm or playful / uplift | 94–100 | if heritage |

## 2. Palette recipe

1. Find the official brand color(s). If only a logo is known, estimate the hex and say so.
2. `brand` = official color. `deep` = the same hue darkened to ~15–25% lightness (backgrounds).
3. `accent` = the premium partner color. Default: champagne gold `#C9A36A`. Use the brand color itself as accent only when the brand is youthful/bold.
4. `dark` = near-black tinted toward the brand hue (e.g. `#0C0D0F`, `#07090D`, `#120A0A`).
5. `light` = off-white tinted warm (`#ECE9E3`) or cool (`#EEF2F0`).
6. Contrast check: `brand` must read on `light` (logo), `accent` must differ from `dark` and `deep`.

Avoid: pure saturated RGB fills, rainbow palettes, neon glow on everything, pure white or pure black backgrounds.

## 3. Story arc (Part I)

Pick 4–5 beats that show the company's real journey. Template:
1. **origin** — where and how it started (humble object, place, founders or capital)
2. **milestone** ×1–2 — the first product/breakthrough; the product that reached the masses (use a `counter` if there is a tangible metric)
3. **city** — scale: listing, national reach, "millions of homes/users"
4. **network** — today's ecosystem (businesses / product lines as nodes)
5. **bridge** — one line that turns from past to future

Emotional rule: first one family / one person / one object, then the city, then the world. Warm → brand color.

## 4. Future (Part II)

Every section is a claim about the future/present strength. Map businesses to sections:
- `slam`: the thesis. "不止于 [X] / 更是 Y" — X = what people think the company is, Y = what it is becoming.
- `shapes`: 8 single characters/words that summarize value (风/冷/智… or SPEED/SAFETY…).
- `grid`: manufacturing / data / platform.
- `cloud`: infrastructure / B2B / cloud / buildings / energy.
- `ribbon`: precision / robotics / logistics / design. Set `"arm": false` if not industrial.
- `words`: all business lines in rows and rings; put a human line in the inner ring (温度 · 风 · 光 · 家).
- `numbers`: 1–2 verified headline facts.
- `logo`: wordmark + real slogan + tagline.

Drop sections that don't fit rather than forcing them. Keep total ≤ 90 s.

## 5. Directing rules

- Rhythm: Part I scenes 3–5 bars each; the bridge is a breath (energy dip); Part II hard-cuts every bar with a new visual language every 2 bars. The dip before the drop is what makes the climax land — never remove the bridge.
- Continuity: the bridge dot *is* the Part II opening dot; the music motif returns at the end.
- Text: one idea per caption, ≤ 2 lines, large and calm in Part I, bold and kinetic in Part II.
- Honesty: only real facts; typeset wordmark (tell the user to replace with the official logo file); no competitor names; no imitation of other brands' identities.
