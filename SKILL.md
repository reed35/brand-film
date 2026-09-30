---
name: brand-film
description: Generate a complete brand/corporate promo video (≤90 s, 1080p, original music) for a company purely with code — no video, image or music models. Use when the user gives a company name (e.g. "美的集团", "Patagonia", "做一个比亚迪的宣传片") and wants a brand film, promo video, company history video, 宣传片, 品牌片 or motion reel. Researches the company, derives a style matched to its brand, writes a film.json, renders with the bundled numpy/Pillow/ffmpeg engine, and returns the MP4.
---

# Brand Film

Turn a company name into a finished two-part brand film:

- **Part I · 叙事篇** (story, ~45–55 s, ~96 BPM): origin → milestones → scale → ecosystem, warm → brand colors, crossfades.
- **Bridge**: everything falls away to one glowing dot; music breathes, then a riser.
- **Part II · 未来篇** (kinetic, ~25–32 s, 128 BPM): hard cut every bar, colour-field slams, material shapes, point clouds, type rings, numbers, logo resolve.
- One original score for both halves (same motif, slow → fast), synthesized in numpy.
- Hard limit: **total ≤ 90 s** (the validator enforces it).

The engine is config-driven: you research, write `film.json`, run commands, look at contact sheets, fix, render.

## Requirements

Python 3.9+ with `pip install numpy pillow imageio-ffmpeg` (ffmpeg binary comes with imageio-ffmpeg). A CJK font is required for Chinese text (Windows/macOS have one; on Linux install Noto Sans CJK). Check with:

```bash
python scripts/make_film.py doctor
```

## Workflow

Follow these steps in order. Do not skip the contact-sheet review.

### 1. Research the company (5–10 min)

Use web search if available. Collect, with sources:
- founding year, city, founders' story in one line; 4–6 milestones with years
- main businesses / product lines (for the network nodes, shapes, word rings)
- scale facts **only if verifiable** (countries, employees, users, rankings)
- brand identity: official colors (hex if published), slogan, sub-brands, tone (heritage / premium / playful / engineering…)

Never invent numbers or events. If something can't be verified, leave it out or phrase it qualitatively. Keep a list of every fact used — you must report it to the user.

### 2. Decide the style

Read `references/style_guide.md`. It maps brand personality → palette roles, mood, BPM, theme, nostalgia grade, and which Part II sections to use. Principles:
- Brand main color stays recognizable, but used with restraint (premium ≠ saturated glow everywhere).
- Pick an accent that fits the brand's premium line (metallic gold/champagne, silver, a deep tone).
- Young companies (< ~15 years) → `"nostalgia": false`; heritage brands → warm sepia opening.
- Match `music.mood` to the brand (warm / luxury / tech / playful / epic).

### 3. Write film.json

Create a working folder (e.g. `./<company>_film/`) and write `film.json` there. Start from `references/example_midea.json`; full field reference is in `references/film_schema.md`.

Text rules: short lines (title ≤ 14 CJK chars / 28 Latin), one idea per caption, write in the user's language (bilingual labels are fine in Part II).

### 4. Validate

```bash
python scripts/make_film.py validate <dir>/film.json
```

Prints the timeline. Fix every ERROR. Aim for 75–90 s total.

### 5. Music

```bash
python scripts/make_film.py music <dir>/film.json
```

Check the printed RMS curve: Part I should climb, the bridge should dip (~ −19 dB), Part II should jump to about −10 dB.

### 6. Contact sheets — look before rendering

```bash
python scripts/make_film.py sheet <dir>/film.json
```

Open `out/sheet_*.jpg` (view the images if you can; otherwise ask the user to look). Check:
- text overlapping graphics or other text; text cut off at edges
- over-exposed or too-dark frames; unreadable text on its background
- palette feels like the brand; no cheap flat saturated fills
Fix `film.json` (shorter text, different icon, palette tweak) and re-run `sheet`. For single frames: `stills <film.json> 12.5,40`.

### 7. Render

Optional quick draft (12 fps, ~1 min): `video <film.json> --draft`. Final:

```bash
python scripts/make_film.py video <dir>/film.json
```

Output: `<dir>/out/<output_name>_1080p.mp4` (1920×1080, 30 fps, H.264 + AAC). About 4–6 min for 60–90 s of film on 16 cores; allow more time on fewer cores.
Only if the user asks for a smaller/faster file: add `--res 720` (or `"resolution": "720p"` in film.json) — about twice as fast, visibly softer.

### 8. Deliver

Give the user:
1. the MP4 path (and send the file if your environment can)
2. a timeline table (time · scene · content)
3. the style decisions (palette, mood, why they fit the brand)
4. **facts to verify** — every year/number/claim used, with sources
5. caveats: the wordmark is typeset text, not the official logo; colors approximate the brand unless official hex values were found; you reviewed stills, not full playback (unless you did)

## Going beyond the templates

For a hero moment the library can't express (a specific product, a landmark), write a custom scene: `{"type": "custom", "module": "my_scenes.py", "func": "hero", "bars": 3}`. The function receives `(t, local_t, scene_dict, timeline)` and returns a `Frame`. See `references/film_schema.md` → Custom scenes for the drawing API. Use at most one or two; test them with `stills`.

## Files

- `scripts/make_film.py` — CLI (doctor / validate / music / stills / sheet / video / all)
- `scripts/bf_core.py` — canvas, text, materials, grading
- `scripts/bf_scenes.py` — scene library and 30 line icons
- `scripts/bf_score.py` — timeline, harmony, drum and cue generation
- `scripts/bf_music.py` — synthesizer and arranger
- `references/film_schema.md` — every film.json field
- `references/style_guide.md` — brand → style decisions, directing rules
- `references/example_midea.json` — complete example
