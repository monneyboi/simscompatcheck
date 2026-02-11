# Sims 1 Compatibility Checker

A tool to help players of The Sims 1 (Complete Collection / Legacy) figure out which sims should talk to whom, based on shared interests.

## Architecture

```
┌─────────────────────┐       ┌──────────────────────┐
│  Svelte Frontend    │──────▶│  FastAPI Backend      │
│  (static, Vite)     │  HTTP │  (Python, reads IFF)  │
│  port 5173          │◀──────│  port 8000            │
└─────────────────────┘       └──────────────────────┘
                                       │
                                       ▼
                              ┌──────────────────────┐
                              │  UserData/            │
                              │  └ Neighborhood.iff   │
                              └──────────────────────┘
```

- **Backend**: Python + FastAPI. Parses IFF files on-the-fly from `UserData/`. No database.
- **Frontend**: Svelte + Vite. Minimal wireframe style with an accent color for actions.
- **Data source**: `UserData/Neighborhood.iff` contains all sim data (NBRS, FAMI, FAMs chunks).

## Running

```bash
# Backend (from project root)
uv run fastapi dev api/main.py

# Frontend (from frontend/)
cd frontend && npm run dev
```

## IFF File Format

IFF is a chunk-based binary format. All data we need lives in `UserData/Neighborhood.iff`.

### Chunk framing (Big-Endian header)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 60 | ASCII header: `"IFF FILE 2.5:TYPE FOLLOWED BY SIZE..."` |
| 60 | 4 | Resource map offset (unused, 0) |
| 64+ | ... | Chunks repeating |

Each chunk:

| Offset | Size | Endian | Field |
|--------|------|--------|-------|
| 0 | 4 | Big | Chunk type (ASCII, e.g. `"NBRS"`) |
| 4 | 4 | Big | Chunk size (includes this 76-byte header) |
| 8 | 2 | Big | Chunk ID |
| 10 | 2 | Big | Chunk flags |
| 12 | 64 | Big | Chunk label (null-padded ASCII) |
| 76 | size-76 | Little | Chunk data |

### NBRS chunk (all sim data)

All chunk data is **Little-Endian**.

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Pad (0) |
| 4 | 4 | Version (0x49) |
| 8 | 4 | Magic (`"SRBN"`) |
| 12 | 4 | Neighbour count |

Each neighbour entry:

| Field | Size | Notes |
|-------|------|-------|
| unknown1 | int32 | Must be 1 for valid entry |
| version | int32 | 0x4 or 0xA |
| unknown3 | int32 | Only if version == 0xA (value 9) |
| name | null-terminated string | If `len(name) % 2 == 0`, skip 1 extra padding byte |
| mystery_zero | int32 | Always 0 |
| person_mode | int32 | 0 = no data, >0 = has PersonData |
| PersonData | short[] | 88 entries, padded to 0x200 bytes (ver 0xA) or 0xA0 bytes (ver 0x4) |
| neighbour_id | int16 | Unique sim ID |
| guid | uint32 | Global unique ID, links to FAMI |
| unknown_neg_one | int32 | Usually -1 |
| relationship_count | int32 | |
| relationships | variable | Per relationship: key_count(i32) + key(i32) + value_count(i32) + values(i32[]) |

### PersonData indices (short[88])

**Personality (0-1000 scale):**
- `[2]` Nice
- `[3]` Active
- `[5]` Playful
- `[6]` Outgoing
- `[7]` Neat

**Interests (0-1000 scale, sometimes 0-10 for user-created sims):**
- `[46]` Travel (adults) / Toys (children)
- `[47]` Violence (adults) / Aliens (children)
- `[48]` Politics (adults) / Pets (children)
- `[49]` 60s/70s (adults) / School (children)
- `[50]` Weather
- `[51]` Sports
- `[52]` Music
- `[53]` Outdoors

**Other useful fields:**
- `[58]` PersonsAge (9 = child, 27+ = adult)
- `[61]` FamilyNumber
- `[65]` Gender (0 = male, 1 = female)

**Scale note:** Pre-made sims use 0-1000, user-created sims may use 0-10. Normalize all to 0-1000 during parsing (if max value in a sim's interests is ≤ 10, multiply by 100).

### FAMI chunk (family definition)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Pad |
| 4 | 4 | Version (0x9) |
| 8 | 4 | Magic (`"IMAF"`) |
| 12 | 4 | House number (0 = not placed) |
| 16 | 4 | Family number |
| 20 | 4 | Budget |
| 24 | 4 | Value in architecture |
| 28 | 4 | Family friends count |
| 32 | 4 | Flags |
| 36 | 4 | GUID count |
| 40+ | 4 each | GUIDs of family members |

### FAMs chunk (family name — STR format -3/0xFFFD)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 2 | Format code (int16, -3 = 0xFFFD) |
| 2 | 2 | String count |

Per string (format -3):
- 1 byte: language code
- null-terminated string: value (the family name)
- null-terminated string: comment (usually empty)

## REST API

### `GET /api/sims`

Returns all sims in the neighborhood with their data.

```json
{
  "sims": [
    {
      "id": 19,
      "guid": "0x7757D9EE",
      "name": "user00023",
      "family_name": "Goth",
      "family_id": 5,
      "house_number": 5,
      "age": "child",
      "gender": "female",
      "personality": {
        "nice": 500,
        "active": 300,
        "playful": 800,
        "outgoing": 600,
        "neat": 200
      },
      "interests": {
        "travel": 200,
        "violence": 100,
        "politics": 100,
        "sixties": 200,
        "weather": 1000,
        "sports": 1000,
        "music": 900,
        "outdoors": 500
      }
    }
  ]
}
```

Only includes sims that have PersonData (person_mode > 0). Interests and personality are normalized to 0-1000 scale.

The `age` field is `"child"` if PersonsAge < 18, `"adult"` otherwise.

### `GET /api/sims/{sim_id}/compatibility`

Returns a ranked list of other sims sorted by compatibility with the selected sim.

```json
{
  "sim_id": 19,
  "rankings": [
    {
      "sim": { /* same shape as above */ },
      "score": 850,
      "common_interests": ["weather", "sports"],
      "risky_topics": ["violence"],
      "relationship_daily": 30,
      "relationship_lifetime": 25,
      "is_friend": false
    }
  ]
}
```

**Compatibility algorithm (100% interest-based):**

Based on actual game mechanics decoded from BHAV behavior scripts in `GameData/`. In The Sims 1, conversation is entirely interest-based — personality only gates which interactions are available (e.g., Nice > 300 to Compliment, Playful ≥ 400 to Tickle), it does not affect relationship score deltas. Zodiac signs (PersonData[70]) are purely cosmetic and never read by any game script.

The game uses 15 interest topics: 8 base game (travel, violence, politics, sixties, weather, sports, music, outdoors from PersonData[46-53]) and 7 Hot Date (exercise, food, parties, style, hollywood, technology, romance from PersonData[13-14, 16, 20, 26, 54-55]).

The game threshold is 400 on the 0-1000 scale (equivalent to 4 on the 0-10 scale): at or above is positive, below is negative.

For each of the 15 topics, compare both sims' values:
- **Common interest** (both ≥ 400): bonus = `min(val_a, val_b)` — stronger shared passion scores higher
- **Risky topic** (one ≥ 400, other < 400): penalty = `abs(val_a - val_b)` — bigger gap means more friction
- **Mutual disinterest** (both < 400): no effect — neither sim cares

Raw sum is normalized from `[-15000, +15000]` to `[0, 1000]`.

### `GET /api/families`

Returns all families.

```json
{
  "families": [
    {
      "id": 5,
      "name": "Goth",
      "house_number": 5,
      "budget": 2542,
      "member_guids": ["0xC07F6184", "0xC0C6298E", "0xC1207913"]
    }
  ]
}
```

## Frontend

### Pages

**Single page app** with one view:

1. **Sim selector** — dropdown or list of all sims (grouped by family)
2. **Compatibility rankings** — when a sim is selected, show ranked list of best conversation partners
   - Each entry shows: sim name, family, score bar, common interests (green), risky topics (red)

### Style

- Wireframe aesthetic: white background, dark text, minimal borders
- Single accent color (blue, `#2563eb`) for interactive elements (buttons, links, selected states)
- Use CSS grid/flex, no CSS framework
- Monospace font for data, sans-serif for labels

## Project structure

```
simscompatcheck/
├── CLAUDE.md
├── pyproject.toml
├── api/
│   ├── main.py          # FastAPI app, mounts routes
│   ├── iff_parser.py    # IFF binary parser (NBRS, FAMI, FAMs)
│   └── compatibility.py # Scoring algorithm
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.svelte
│       ├── main.js
│       └── app.css
└── UserData/            # Sims 1 save files (gitignored)
```

## Dependencies

**Python** (managed by uv):
- fastapi
- uvicorn

**Frontend** (managed by npm):
- svelte
- vite
- @sveltejs/vite-plugin-svelte
