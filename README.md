# wc-progression

Daily, market-calibrated progression numbers for the "Race to 21" World Cup trackers.

Every morning a GitHub Action runs `refresh_progression.py`, which:
1. pulls the current World Cup match odds (one bookmaker, via The Odds API),
2. simulates every group forward from those odds plus the results so far,
3. works out each team's live chance of reaching the knockouts (top two per group, plus the eight best third-placed teams),
4. commits the result to `progression.json`.

The trackers fetch `progression.json` straight from this repo (a public, keyless URL) and use it in place of hand-set progression numbers, so their win/bust odds re-rate themselves as the group tables change.

## Setup (one-off)

1. This repo must be **public** (so the trackers can read `progression.json`).
2. Add your The Odds API key as a secret: **Settings → Secrets and variables → Actions → New repository secret**, name it `ODDS_API_KEY`, paste the key from the-odds-api.com.
3. The Action runs daily on its own. To run it now, go to **Actions → Refresh progression → Run workflow**.

`progression.json` is then served at:
`https://raw.githubusercontent.com/<your-username>/wc-progression/main/progression.json`

## Cost

One Odds API call a day (~1 credit), about 30 a month against the free tier's 500.
