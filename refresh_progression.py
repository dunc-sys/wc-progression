"""Market-calibrated progression for the 21 trackers.

Each team's LIVE chance of reaching the knockouts, derived by simulating every
group forward from the bookmakers' match odds (margin stripped) plus results so
far. Replaces the hand-set progression numbers and re-rates itself as the group
tables change — fixing the trackers' phantom-goals blind spot.

Top two of each group qualify; the 8 best third-placed teams across the 12
groups also go through (ranked by points, goal difference, goals for — modelled
in the same simulation, so no separate heuristic).

Run: python3 refresh_progression.py
  -> writes progression.json: {"France": 0.97, "Senegal": 0.71, ...}
Needs the odds API key in .claude/local/odds-api-key.txt; falls back to a base
Poisson model for any group game not yet priced by the market.
"""
import json, os, math, random, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
N = 20000
HOME_NUDGE = 1.10            # mild home/first-named bump for the fallback model
random.seed(7)

RATES = json.load(open(os.path.join(HERE, "team_rates.json")))
# odds API team names -> openfootball spellings, if they ever differ
ALIAS = {"United States": "USA", "Turkiye": "Turkey", "Czechia": "Czech Republic",
         "Bosnia and Herzegovina": "Bosnia & Herzegovina"}

def norm(t): return ALIAS.get(t, t)

def pois(lam, k): return math.exp(-lam) * lam**k / math.factorial(k)

def model_1x2(la, lb, maxg=8):
    ph = pd = pa = 0.0
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            p = pois(la, i) * pois(lb, j)
            if i > j: ph += p
            elif i == j: pd += p
            else: pa += p
    return ph, pd, pa

def strip_1x2(h, d, a):
    ih, idr, ia = 1/h, 1/d, 1/a
    s = ih + idr + ia
    return ih/s, idr/s, ia/s

def load_odds():
    """{(home,away): (decH,decD,decA)} for upcoming games, via fetch_odds.py."""
    try:
        out = subprocess.run(["python3", os.path.join(HERE, "fetch_odds.py")],
                             capture_output=True, text=True, timeout=40)
        data = json.loads(out.stdout) if out.stdout.strip() else []
    except Exception:
        return {}
    d = {}
    for m in data:
        o = m["odds"]
        if {"A_win", "draw", "B_win"} <= set(o):
            d[(norm(m["home"]), norm(m["away"]))] = (o["A_win"], o["draw"], o["B_win"])
    return d

def prob(t1, t2, odds):
    if (t1, t2) in odds:
        return strip_1x2(*odds[(t1, t2)])
    if (t2, t1) in odds:                       # reversed listing
        ph, pd, pa = strip_1x2(*odds[(t2, t1)]); return pa, pd, ph
    la = RATES.get(t1, {}).get("group_rate", 1.0) * HOME_NUDGE
    lb = RATES.get(t2, {}).get("group_rate", 1.0)
    return model_1x2(la, lb)

def sample_score(outcome):
    if outcome == "D":
        g = random.choice([0, 1, 1, 2]); return g, g
    margin = random.choice([1, 1, 1, 2, 2, 3]); loser = random.choice([0, 0, 1])
    return (margin + loser, loser) if outcome == "H" else (loser, margin + loser)

def apply(pts, gd, gf, t1, t2, g1, g2):
    gd[t1] += g1 - g2; gd[t2] += g2 - g1; gf[t1] += g1; gf[t2] += g2
    if g1 > g2: pts[t1] += 3
    elif g2 > g1: pts[t2] += 3
    else: pts[t1] += 1; pts[t2] += 1

def main():
    M = json.load(urllib.request.urlopen(DATA_URL))["matches"]
    groups = {}
    for m in M:
        g = m.get("group", "")
        if not g.startswith("Group"): continue
        L = g.split()[-1]
        gd = groups.setdefault(L, {"teams": set(), "played": [], "remaining": []})
        gd["teams"].update([m["team1"], m["team2"]])
        if m.get("score"):
            ft = m["score"]["ft"]
            gd["played"].append((m["team1"], m["team2"], ft[0], ft[1]))
        else:
            gd["remaining"].append((m["team1"], m["team2"]))

    odds = load_odds()
    all_teams = [t for gd in groups.values() for t in gd["teams"]]
    qual = {t: 0 for t in all_teams}

    for _ in range(N):
        thirds = []
        for gd in groups.values():
            pts = {t: 0 for t in gd["teams"]}
            gdi = {t: 0 for t in gd["teams"]}
            gf = {t: 0 for t in gd["teams"]}
            for t1, t2, g1, g2 in gd["played"]:
                apply(pts, gdi, gf, t1, t2, g1, g2)
            for t1, t2 in gd["remaining"]:
                ph, pd, pa = prob(t1, t2, odds)
                r = random.random()
                out = "H" if r < ph else ("D" if r < ph + pd else "A")
                g1, g2 = sample_score(out)
                apply(pts, gdi, gf, t1, t2, g1, g2)
            ranked = sorted(gd["teams"], key=lambda t: (pts[t], gdi[t], gf[t]), reverse=True)
            qual[ranked[0]] += 1; qual[ranked[1]] += 1
            thirds.append((pts[ranked[2]], gdi[ranked[2]], gf[ranked[2]], ranked[2]))
        thirds.sort(reverse=True)
        for _, _, _, t in thirds[:8]:
            qual[t] += 1

    result = {t: round(qual[t] / N, 3) for t in sorted(all_teams)}
    with open(os.path.join(HERE, "progression.json"), "w") as f:
        json.dump(result, f, indent=0, ensure_ascii=False)
    priced = sum(1 for gd in groups.values() for r in gd["remaining"]
                 if (r[0], r[1]) in odds or (r[1], r[0]) in odds)
    total_rem = sum(len(gd["remaining"]) for gd in groups.values())
    print(f"progression.json written: {len(result)} teams, "
          f"{priced}/{total_rem} remaining games priced by market (rest use fallback model)")

if __name__ == "__main__":
    main()
