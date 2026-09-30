# film.json reference

All text fields are optional unless marked **required**. Times are derived from bars; you never write seconds.

## Top level

| field | example | notes |
|---|---|---|
| `company` **required** | `"美的集团"` | used as fallback wordmark / HUD name |
| `hud_name` | `"Midea Group"` | Latin name shown in the Part II corner HUD (upper-cased) |
| `output_name` | `"midea_brand_film"` | MP4 file name |
| `out_dir` | `"out"` | relative to film.json |
| `resolution` | `"1080p"` | `"1080p"` (1920×1080, default, sharpest) or `"720p"` (1280×720, ~2× faster, softer). CLI `--res` overrides |
| `years` | `"1968 — 2026"` | founding year — current year |
| `wordmark` | `{"text": "美的", "latin": "Midea"}` | typeset in the final logo resolve; `latin` optional |
| `slogan` | `"科技尽善  ·  生活尽美"` | under the wordmark; only use the real slogan |
| `tagline` | `"从一只瓶盖，到全球智造"` | small line under the slogan: the film's arc in one sentence |
| `palette` | see below | hex colors |
| `grade` | `{"nostalgia": true, "warm_until": 32}` | sepia/grain opening that fades out by `warm_until` seconds (default 70% of Part I) |
| `music` | `{"key": "C", "bpm1": 96, "bpm2": 128, "mood": "warm", "theme": "uplift"}` | see Music |
| `fonts` | `{"b": "path", "r": "...", "l": "...", "en": "...", "enl": "..."}` | override auto-detected fonts (b=CJK bold, r=regular, l=light, en=Latin bold, enl=Latin light) |
| `part1` **required** | `{"scenes": [...]}` | |
| `part2` **required** | `{"sections": [...]}` | |

## Palette roles

| role | used for | guidance |
|---|---|---|
| `dark` | Part II dark sections, bridge | near-black, slightly tinted (obsidian, ink) |
| `light` | grid, logo backgrounds | warm/cool off-white, never pure #FFF |
| `deep` | Part I night/network scenes, point cloud, first number | deep version of the brand hue |
| `accent` | dots, slam background, materials, highlights | the premium accent: champagne gold, copper, silver, jade… |
| `brand` | wordmark, one highlighted word in the slam, ribbon core stripe | the official brand color |
| `metal` | ribbon section brushed background | light metallic grey |
| `warm` | Part I nostalgic highlights | amber |
| `text_dark` / `text_light` | text on light / dark backgrounds | chosen automatically by background luminance |
| `muted` | hairlines, HUD, secondary labels | mid grey |

## Music

- `key`: `"C"`…`"B"` (Part II plays a whole step higher automatically)
- `bpm1`: Part I tempo, 84–104. `bpm2`: Part II tempo, 120–132 (128 recommended)
- `mood`: `warm` (music box, piano, brass; vinyl crackle if nostalgia) · `luxury` (piano, strings, no brass stabs) · `tech` (bells, plucks early) · `playful` (music box + plucks) · `epic` (strings + brass heavy)
- `theme`: `uplift` (hopeful, flowing) · `noble` (slow, stately) · `bright` (energetic, leaps)

## Part 1 scenes (`part1.scenes`, in order)

Each has `type` and `bars` (1 bar ≈ 2.5 s at 96 BPM). Energy (drums, layers) rises automatically across Part I; override with `"energy": 0-3`.

### origin — the humble beginning (3 bars)
`year`, `place`, `title`, `side` (1–2 lines on the right, e.g. founding capital), `icon` (object on the workbench).
A bulb flickers on over a workbench; dust in the light cone.

### milestone — an era, 1–3 beats (3 bars)
`items`: list of `{year, title, sub, icon, counter?}` shown in sequence within the scene; `flow`: `wind` | `rise` | `orbit` | `none`.
`counter`: `{"from": 35, "to": 26, "suffix": "°", "decimals": 0}` — a big number that animates (temperature, capacity, users…).
Background shifts from warm to brand-deep as the film advances.

### city — reaching everyone (4–5 bars)
`year`, `title`, `sub`, `text` (centered line in the second half). Pull back from one lit window to a whole skyline lighting up. Good for "millions of homes", IPO, national scale.

### network — ecosystem (4 bars)
`year`, `title`, `sub`, `lines2` (caption for the second half), `hub` (≤ 4 chars on the hub), `nodes`: list of `{label, icon}` (4–7).

### bridge — the breath (always 2 bars, added automatically if missing)
`text`: e.g. "而这，只是开始" / "And this is only the beginning". Must be last.

### custom — your own scene
`module` (python file next to film.json), `func`, `bars`, plus any fields your function reads.

## Part 2 sections (`part2.sections`, in order)

Bars are fixed per type. Must start with `dots` and end with `logo`. Typical: dots, slam, shapes, grid, cloud, ribbon, words, numbers, logo (17 bars ≈ 32 s). Drop sections to shorten.

| type | bars | background | fields |
|---|---|---|---|
| `dots` | 2 | dark | — (the bridge dot divides, orbits, floods the frame) |
| `slam` | 2 | accent | `line1`, `box` (bracketed word), `line2a`, `line2b` (highlighted in brand color), `label` (small caps line) |
| `shapes` | 2 | dark | `items`: 8 × `[big_char_or_word, "LABEL"]`, `caption`. Circle→square→triangle… in accent/metal/deep/light materials |
| `grid` | 2 | light | `title`, `label`, `subs` [first bar, second bar]. Dot field with data paths, tilts to 3D |
| `cloud` | 2 | deep | `title`, `label`, `subs`. 900-point cloud: sphere → torus → lattice |
| `ribbon` | 2 | metal (brushed) | `title`, `sub`, `subs`, `arm` (true = a two-link robot arm draws the ribbon; set false for non-industrial brands) |
| `words` | 2 | dark | `rows` (3–5 marquee lines), `rings` (3 ring texts: outer big, middle small, inner accent) |
| `numbers` | 1 | deep, then accent | `items`: 1–2 × `[big_number, label]` — verifiable facts only |
| `logo` | 2 | light | uses top-level `wordmark`, `slogan`, `tagline`, `years` |
| `custom` | `bars` | yours | `module`, `func` |

## Icons (for `icon` fields)

`fan ac bulb house gear chip phone car globe leaf box cup plane heart chart bolt battery screen cart factory drop star wifi pill book fridge washer robot spark wind cap`

Pick the closest metaphor (bank → `chart`, logistics → `box`, food → `cup`, pharma → `pill`, EV → `battery`/`car`, software → `screen`/`chip`, energy → `bolt`/`leaf`).

## Custom scenes

```python
# my_scenes.py (next to film.json)
import math
from bf_core import *          # Frame, bg_for, grad_bg, caption, center_title, rgba, mix, PAL, CFG, ease_*, sstep ...
from bf_scenes import draw_icon, pulse

def hero(t, lt, s, tl):
    fr = Frame(bg_for(PAL['deep']))          # 4K supersampled base
    cv, lv = fr.cv(z=1 + .05 * lt), fr.lv()   # cv: sharp layer, lv: glow layer (both in 1920x1080 coords)
    cv.ellipse(960, 540, 200, outline=rgba(PAL['accent'], .8), width=2)
    lv.ellipse(960, 540, 260, fill=rgba(PAL['accent'], .3))
    fr.mat(circle_pts(960, 540, 120), 'accent')               # metallic material disc
    caption(fr, t, tl.b1(s['bar0']) + .3, tl.b1(s['bar0'] + s['bars']), s.get('year', ''), [s.get('title', '')])
    fr.text('HELLO', 960, 900, 60, PAL['text_light'], 1, key='en', anchor='m', track=.2)
    return fr
```

Canvas methods: `ellipse, line, poly, rect(r=radius)`; colors via `rgba(rgb, alpha)`. Materials: `'accent' 'brand' 'deep' 'metal' 'light' 'dark' 'gold' 'silver'`. `pulse(t)` returns a 0–1 kick-drum envelope for beat-synced motion.
