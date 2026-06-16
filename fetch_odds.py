"""Pull World Cup 1X2 odds from The Odds API for ONE bookmaker (bet365), so
every game is priced from the same source and the engine can strip that book's
margin cleanly. No more reading prices off aggregators by hand.

One-off setup: sign up free at https://the-odds-api.com (500 credits/month),
copy your API key into:
  /Users/duncanmcilroy/Desktop/dunc-cws/.claude/local/odds-api-key.txt

Cost: credits = markets x regions per call. One uk + h2h pull = 1 credit, so a
daily tip is ~30 credits/month, well inside the free 500. Adding totals = 2/day.

Run:
  python3 fetch_odds.py           # all upcoming WC matches, bet365 1X2 (h2h)
  python3 fetch_odds.py totals    # also pull over/under 2.5 (costs +1 credit)

Output: JSON list, one per match, A = home team, B = away team:
  [{"home":"France","away":"Senegal","commence":"2026-06-16T19:00:00Z",
    "odds":{"A_win":1.53,"draw":4.5,"B_win":7.75}}, ...]
Feed each into match_value.py after setting lamA (home xG) and lamB (away xG).
"""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SPORT, REGION = "soccer_fifa_world_cup", "uk"

def get_key():
    """Cloud: ODDS_API_KEY env var. Local: the .claude/local key file."""
    k = os.environ.get("ODDS_API_KEY")
    if k and k.strip():
        return k.strip()
    for p in (os.path.join(HERE, "odds-api-key.txt"),
              "/Users/duncanmcilroy/Desktop/dunc-cws/.claude/local/odds-api-key.txt"):
        if os.path.exists(p):
            return open(p).read().strip()
    sys.exit("NO KEY: set the ODDS_API_KEY env var, or create odds-api-key.txt (free key at the-odds-api.com).")
# bet365 is NOT in The Odds API uk feed. Use a mainstream proxy that prices like
# it (margin gets stripped anyway). First available per match, in this order:
BOOKS = ["bet365", "williamhill", "skybet", "paddypower", "ladbrokes_uk",
         "coral", "betfred_uk", "unibet_uk", "betvictor"]

def main():
    key = get_key()
    markets = "h2h,totals" if (len(sys.argv) > 1 and sys.argv[1] == "totals") else "h2h"
    url = (f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
           f"?apiKey={key}&regions={REGION}&markets={markets}&oddsFormat=decimal")
    try:
        with urllib.request.urlopen(url) as r:
            remaining = r.headers.get("x-requests-remaining")
            data = json.load(r)
    except Exception as e:
        sys.exit(f"the-odds-api request failed: {e}")

    out = []
    for m in data:
        bk = None
        for pref in BOOKS:
            bk = next((x for x in m.get("bookmakers", []) if x["key"] == pref), None)
            if bk:
                break
        if not bk:
            continue
        rec = {"home": m["home_team"], "away": m["away_team"],
               "commence": m["commence_time"], "book": bk["title"], "odds": {}}
        h2h = next((mk for mk in bk["markets"] if mk["key"] == "h2h"), None)
        if h2h:
            for o in h2h["outcomes"]:
                if o["name"] == m["home_team"]: rec["odds"]["A_win"] = o["price"]
                elif o["name"] == m["away_team"]: rec["odds"]["B_win"] = o["price"]
                else: rec["odds"]["draw"] = o["price"]
        tot = next((mk for mk in bk["markets"] if mk["key"] == "totals"), None)
        if tot:
            for o in tot["outcomes"]:
                if abs(o.get("point", 0) - 2.5) < 0.01:
                    if o["name"] == "Over": rec["odds"]["over25"] = o["price"]
                    elif o["name"] == "Under": rec["odds"]["under25"] = o["price"]
        if {"A_win", "draw", "B_win"} <= set(rec["odds"]):
            out.append(rec)

    print(json.dumps(out, indent=2, ensure_ascii=False))
    if remaining:
        print(f"# the-odds-api credits remaining this month: {remaining}", file=sys.stderr)

if __name__ == "__main__":
    main()
