#!/usr/bin/env python3
"""
ProjX House & Land Design Portal — V2.4
Map-first UX with real Monday.com data from Contract Administration workspace
Fetches H&L project boards only, shows Available/Unreleased lots only
"""

import json, os, sys, urllib.request, datetime

API_URL = "https://api.monday.com/v2"
WORKSPACE_ID = 2429759

# H&L-only allowlist — exclude townhouse/apartment projects
HL_ALLOWLIST = {
    'Oakland Estate',
    'Woodchester',
    'Fox & Shipper',
    'Lakeview Estate',
    'Brookdale',
    'Sorensen Rise',
    'Riverina',
    'At Nineteen',
    'North Pine Golf Estate',
    'Eade',
    'Harvest',
    'Elio',
    'The Gables',
    'Serenity',
}

EXCLUDED_BOARDS = {
    'Bliss on Bracken',
    'Residences on Main',
    'Leaf Residences',
    'Mountview Terraces',
    'Co Living Australia',
    'The Reserve',
    'Grove on Goodfellows',
}

# Only Available and Unreleased lots are shown
VISIBLE_STATUSES = {'Available', 'Unreleased'}

PROJECTS_GEO = {
    'Oakland Estate': {'suburb': 'Beaudesert', 'lat': -27.99, 'lng': 152.97, 'region': 'Scenic Rim'},
    'Woodchester': {'suburb': 'Gatton', 'lat': -27.55, 'lng': 152.28, 'region': 'Lockyer Valley'},
    'Fox & Shipper': {'suburb': 'Coomera', 'lat': -27.86, 'lng': 153.35, 'region': 'Gold Coast'},
    'Lakeview Estate': {'suburb': 'Gatton', 'lat': -27.56, 'lng': 152.27, 'region': 'Lockyer Valley'},
    'Brookdale': {'suburb': 'Park Ridge', 'lat': -27.72, 'lng': 153.04, 'region': 'Logan'},
    'At Nineteen': {'suburb': 'Burpengary', 'lat': -27.16, 'lng': 152.95, 'region': 'Moreton Bay'},
    'North Pine Golf Estate': {'suburb': 'Joyner', 'lat': -27.24, 'lng': 152.93, 'region': 'Moreton Bay'},
    'Eade': {'suburb': 'Byron Bay', 'lat': -28.64, 'lng': 153.62, 'region': 'Northern NSW'},
    'Harvest': {'suburb': 'Byron Bay', 'lat': -28.65, 'lng': 153.61, 'region': 'Northern NSW'},
    'Elio': {'suburb': 'North Mackay', 'lat': -21.13, 'lng': 149.17, 'region': 'Mackay'},
    'The Gables': {'suburb': 'Loganholme', 'lat': -27.67, 'lng': 153.20, 'region': 'Logan'},
    'Serenity': {'suburb': 'Beerwah', 'lat': -26.85, 'lng': 152.97, 'region': 'Sunshine Coast'},
    'Riverina': {'suburb': 'Carrara', 'lat': -28.02, 'lng': 153.37, 'region': 'Gold Coast'},
    'Sorensen Rise': {'suburb': 'Southside', 'lat': -26.20, 'lng': 152.65, 'region': 'Gympie'},
}

REGION_ORDER = [
    'Gold Coast', 'Logan', 'Moreton Bay', 'Lockyer Valley',
    'Scenic Rim', 'Sunshine Coast', 'Gympie', 'Mackay', 'Northern NSW',
]


def get_token():
    env_path = os.path.expanduser("~/.openclaw/workspace/.env")
    with open(env_path) as f:
        for line in f:
            if line.startswith("MONDAY_API_TOKEN="):
                return line.strip().split("=", 1)[1].strip()
    raise RuntimeError("MONDAY_API_TOKEN not found in .env")


def monday_query(query, token):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "Authorization": token},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_workspace_boards(token):
    """Fetch all boards in the Contract Administration workspace."""
    q = '{boards(workspace_ids: [%d], limit: 50) { id name }}' % WORKSPACE_ID
    data = monday_query(q, token)
    return data["data"]["boards"]


def make_slug(name):
    return name.lower().replace(' ', '').replace('&', '').replace("'", "").replace('-', '')


def fetch_board_lots(board_id, board_name, token):
    """Fetch items from a board, auto-detecting availability/price/size columns."""
    col_q = '{boards(ids: [%s]) { columns { id title type }}}' % board_id
    col_data = monday_query(col_q, token)
    columns = col_data["data"]["boards"][0]["columns"]

    avail_col = price_col = size_col = type_col = stage_col = None
    for col in columns:
        t = col["title"].lower()
        ctype = col["type"]
        if avail_col is None and ("availab" in t or t == "status") and ctype in ("color", "dropdown", "status"):
            avail_col = col["id"]
        elif price_col is None and ("price" in t) and ctype in ("numeric", "numbers"):
            price_col = col["id"]
        elif size_col is None and ("size" in t or "area" in t or "sqm" in t) and ctype in ("numeric", "numbers"):
            size_col = col["id"]
        elif type_col is None and ("type" in t) and ctype in ("dropdown", "status", "color"):
            type_col = col["id"]
        elif stage_col is None and ("stage" in t) and ctype in ("dropdown", "status", "color", "text"):
            stage_col = col["id"]

    col_ids = [c for c in [avail_col, price_col, size_col, type_col, stage_col] if c]
    col_ids_str = ('ids: [' + ','.join('"' + c + '"' for c in col_ids) + ']') if col_ids else ""

    items_q = '{boards(ids: [%s]) { items_page(limit: 500) { items { id name group { title } column_values(%s) { id text }}}}}' % (board_id, col_ids_str)
    data = monday_query(items_q, token)
    raw_items = data["data"]["boards"][0]["items_page"]["items"]

    slug = make_slug(board_name)
    lots = []
    for item in raw_items:
        row = {}
        for cv in item["column_values"]:
            if cv["id"] == avail_col:
                row["availability"] = cv["text"] or ""
            elif cv["id"] == price_col:
                row["lot_price"] = cv["text"] or ""
            elif cv["id"] == size_col:
                row["lot_size"] = cv["text"] or ""
            elif cv["id"] == type_col:
                row["type"] = cv["text"] or ""
            elif cv["id"] == stage_col:
                row["stage"] = cv["text"] or ""

        avail = row.get("availability", "")
        lot_size = 0
        try:
            lot_size = float(str(row.get("lot_size", "0")).replace(",", ""))
        except Exception:
            pass
        price = 0
        try:
            price = float(str(row.get("lot_price", "0")).replace(",", ""))
        except Exception:
            pass

        if lot_size > 0:
            frontage = round(lot_size / 28)
        else:
            frontage = 12
        frontage = max(10, min(frontage, 25))

        lots.append({
            "id": item["id"],
            "name": item["name"],
            "availability": avail if avail else "Available",
            "price": int(price),
            "lot_size": int(lot_size),
            "frontage": frontage,
            "type": row.get("type", "H&L"),
            "stage": row.get("stage", "Stage 1"),
            "project": slug,
        })

    # Only keep lots with visible statuses (Available / Unreleased)
    lots = [l for l in lots if l["availability"] in VISIBLE_STATUSES]
    lots.sort(key=lambda x: x["name"])
    return lots


# ── HTML Template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ProjX | House &amp; Land Design Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#001E2E;--navy-mid:#002D44;--navy-light:#003855;
  --silver:#CBD2D8;--silver-light:#E8EBED;--silver-xlight:#F4F5F7;
  --accent:#00A3E0;--accent-dark:#0082B3;--accent-glow:rgba(0,163,224,0.15);
  --green:#10B981;--amber:#F59E0B;--red:#EF4444;--white:#FFFFFF;
  --bg:#F0F2F5;--text:#001E2E;--text-mid:#374151;--text-light:#6B7280;--text-xlight:#9CA3AF;
  --shadow-sm:0 1px 3px rgba(0,30,46,0.08),0 2px 6px rgba(0,30,46,0.04);
  --shadow-md:0 4px 12px rgba(0,30,46,0.1),0 2px 4px rgba(0,30,46,0.06);
  --shadow-lg:0 8px 24px rgba(0,30,46,0.12),0 4px 8px rgba(0,30,46,0.08);
  --shadow-xl:0 16px 48px rgba(0,30,46,0.16),0 8px 16px rgba(0,30,46,0.08);
  --radius:12px;--radius-sm:8px;--radius-lg:16px;--radius-xl:24px;--transition:0.2s ease;
}
body{font-family:'Montserrat',sans-serif;background:var(--bg);color:var(--text);line-height:1.5;min-height:100vh;-webkit-font-smoothing:antialiased}
button{cursor:pointer;font-family:'Montserrat',sans-serif}
input,select,textarea{font-family:'Montserrat',sans-serif}

/* ── Password Gate ── */
#auth-gate{position:fixed;inset:0;z-index:9999;background:var(--navy);display:flex;align-items:center;justify-content:center;flex-direction:column}
#auth-gate.hidden{display:none}
.gate-wrap{text-align:center;max-width:420px;width:90%;padding:0 16px}
.gate-logo{width:56px;height:56px;background:var(--accent);border-radius:16px;display:flex;align-items:center;justify-content:center;margin:0 auto 24px;font-size:22px;font-weight:900;color:#fff;letter-spacing:-1px}
.gate-box{background:#fff;border-radius:var(--radius-xl);padding:40px 36px;box-shadow:var(--shadow-xl)}
.gate-box h2{font-size:20px;font-weight:800;color:var(--navy);margin-bottom:4px}
.gate-box .gate-sub{font-size:13px;color:var(--text-light);margin-bottom:28px}
.gate-badge{display:inline-flex;align-items:center;gap:6px;background:#FEF3C7;color:#92400E;font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:20px}
.gate-input{width:100%;padding:14px 18px;border:2px solid var(--silver-light);border-radius:var(--radius-sm);font-size:16px;text-align:center;letter-spacing:4px;outline:none;transition:border-color var(--transition);color:var(--navy);background:#fff}
.gate-input:focus{border-color:var(--accent)}
.gate-input.error{border-color:var(--red);animation:shake 0.4s}
.gate-btn{margin-top:14px;width:100%;padding:15px;background:var(--navy);color:#fff;border:none;border-radius:var(--radius-sm);font-size:13px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;transition:all var(--transition)}
.gate-btn:hover{background:var(--navy-mid);transform:translateY(-1px)}
.gate-footer{color:rgba(203,210,216,0.5);font-size:11px;margin-top:20px;letter-spacing:0.5px}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-8px)}75%{transform:translateX(8px)}}

/* ── App Shell ── */
#app{display:none;min-height:100vh;flex-direction:column}
#app.visible{display:flex}

/* ── Top Bar ── */
.top-bar{background:var(--navy);padding:0 28px;height:60px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:500;box-shadow:0 2px 16px rgba(0,0,0,0.25)}
.top-bar-left{display:flex;align-items:center;gap:14px}
.top-logo{background:var(--accent);color:#fff;font-size:13px;font-weight:900;padding:6px 12px;border-radius:8px;letter-spacing:-0.3px;cursor:pointer;transition:opacity var(--transition)}
.top-logo:hover{opacity:0.85}
.top-title{color:#fff;font-size:14px;font-weight:700;letter-spacing:-0.3px}
.top-title span{color:var(--silver);font-weight:400;font-size:12px}
.top-bar-right{display:flex;align-items:center;gap:10px}
.confidential-badge{background:rgba(245,158,11,0.15);color:#F59E0B;border:1px solid rgba(245,158,11,0.3);font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px}
.top-home-btn{background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.7);border:none;padding:6px 14px;border-radius:8px;font-size:11px;font-weight:600;transition:all var(--transition);display:none}
.top-home-btn:hover{background:rgba(255,255,255,0.15);color:#fff}
.top-home-btn.visible{display:block}

/* ── Breadcrumb ── */
.breadcrumb-bar{background:#fff;border-bottom:1px solid var(--silver-light);padding:10px 28px;min-height:40px;display:flex;align-items:center}
.breadcrumb{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.bc-item{font-size:12px;font-weight:600;color:var(--text-xlight);transition:color var(--transition)}
.bc-item.clickable{color:var(--accent);cursor:pointer}
.bc-item.clickable:hover{color:var(--accent-dark);text-decoration:underline}
.bc-item.current{color:var(--navy);font-weight:700}
.bc-sep{color:var(--silver);font-size:11px}

/* ── View Container ── */
.view{display:none;flex:1;flex-direction:column;animation:fadeSlideIn 0.3s ease}
.view.active{display:flex}
@keyframes fadeSlideIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

/* ── Landing: Map Hero ── */
#view-landing{flex-direction:column}
.map-section{position:relative}
#map{height:62vh;min-height:380px;width:100%;z-index:1}
.map-overlay-header{
  position:absolute;top:20px;left:50%;transform:translateX(-50%);z-index:10;
  background:rgba(0,30,46,0.85);backdrop-filter:blur(12px);
  padding:14px 28px;border-radius:var(--radius-lg);
  display:flex;flex-direction:column;align-items:center;gap:4px;
  border:1px solid rgba(255,255,255,0.1);
  text-align:center;white-space:nowrap;
}
.map-overlay-header h1{color:#fff;font-size:18px;font-weight:800;letter-spacing:-0.3px}
.map-overlay-header p{color:rgba(203,210,216,0.8);font-size:12px;font-weight:500}
.map-entry-btns{
  position:absolute;bottom:20px;left:50%;transform:translateX(-50%);
  z-index:10;display:flex;gap:12px;
}
.map-entry-btn{
  padding:13px 24px;border-radius:var(--radius);font-size:13px;font-weight:700;
  border:none;display:flex;align-items:center;gap:8px;transition:all 0.2s ease;
  white-space:nowrap;box-shadow:var(--shadow-lg);
}
.map-entry-btn.primary{background:var(--accent);color:#fff}
.map-entry-btn.primary:hover{background:var(--accent-dark);transform:translateY(-2px)}
.map-entry-btn.secondary{background:rgba(255,255,255,0.95);color:var(--navy)}
.map-entry-btn.secondary:hover{background:#fff;transform:translateY(-2px)}
.map-entry-btn svg{flex-shrink:0}

/* Leaflet overrides */
.leaflet-container{font-family:'Montserrat',sans-serif}
.leaflet-popup-content-wrapper{border-radius:var(--radius) !important;box-shadow:var(--shadow-xl) !important;border:none !important;padding:0 !important;overflow:hidden}
.leaflet-popup-content{margin:0 !important;width:240px !important}
.leaflet-popup-tip-container{display:none}
.popup-inner{padding:16px}
.popup-project-name{font-size:14px;font-weight:800;color:var(--navy);margin-bottom:2px}
.popup-suburb{font-size:11px;color:var(--text-light);margin-bottom:12px}
.popup-stats{display:flex;gap:8px;margin-bottom:12px}
.popup-stat{flex:1;background:var(--silver-xlight);border-radius:var(--radius-sm);padding:8px;text-align:center}
.popup-stat-val{font-size:14px;font-weight:800;color:var(--navy)}
.popup-stat-lbl{font-size:9px;font-weight:600;color:var(--text-xlight);text-transform:uppercase;margin-top:1px}
.popup-price{font-size:12px;color:var(--text-light);margin-bottom:10px}
.popup-price strong{color:var(--navy);font-weight:700}
.popup-btn{width:100%;padding:10px;background:var(--navy);color:#fff;border:none;border-radius:var(--radius-sm);font-size:12px;font-weight:700;letter-spacing:0.5px;transition:background var(--transition);cursor:pointer}
.popup-btn:hover{background:var(--accent)}

/* Custom map pin */
.map-pin-wrap{display:flex;flex-direction:column;align-items:center;cursor:pointer}
.map-pin-circle{
  width:44px;height:44px;border-radius:50%;
  background:var(--navy);border:3px solid var(--accent);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 16px rgba(0,30,46,0.4),0 0 0 0 rgba(0,163,224,0.4);
  transition:all 0.2s ease;
  animation:pinPulse 2.5s ease-in-out infinite;
}
.map-pin-circle:hover{transform:scale(1.15);box-shadow:0 6px 20px rgba(0,30,46,0.5)}
.map-pin-label-tag{
  margin-top:4px;background:rgba(0,30,46,0.9);color:#fff;
  font-size:9px;font-weight:700;padding:3px 7px;border-radius:20px;
  white-space:nowrap;letter-spacing:0.3px;
}
@keyframes pinPulse{
  0%,100%{box-shadow:0 4px 16px rgba(0,30,46,0.4),0 0 0 0 rgba(0,163,224,0.4)}
  50%{box-shadow:0 4px 16px rgba(0,30,46,0.4),0 0 0 8px rgba(0,163,224,0)}
}
.map-pin-count{font-size:13px;font-weight:800;color:#fff}

/* ── Map Filter Bar ── */
.map-filter-bar{
  background:#fff;padding:10px 20px;
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  border-bottom:1px solid var(--silver-light);
}
.mfb-group{display:flex;flex-direction:column;gap:3px}
.mfb-label{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-xlight)}
.mfb-chips{display:flex;gap:4px;flex-wrap:wrap}
.mfb-chip{
  padding:6px 12px;border-radius:20px;border:1.5px solid var(--silver-light);
  font-size:11px;font-weight:600;color:var(--text-mid);
  cursor:pointer;transition:all var(--transition);background:#fff;
  white-space:nowrap;
}
.mfb-chip.active{border-color:var(--navy);background:var(--navy);color:#fff}
.mfb-chip:hover:not(.active){border-color:var(--accent);color:var(--accent)}
.mfb-clear{
  font-size:11px;font-weight:600;color:var(--accent);
  cursor:pointer;background:none;border:none;padding:6px 10px;
  transition:color var(--transition);margin-left:auto;white-space:nowrap;
}
.mfb-clear:hover{color:var(--accent-dark);text-decoration:underline}
.mfb-select{
  padding:6px 12px;border:1.5px solid var(--silver-light);border-radius:20px;
  font-size:11px;font-weight:600;color:var(--text-mid);background:#fff;
  outline:none;cursor:pointer;transition:all var(--transition);
}
.mfb-select:focus{border-color:var(--accent)}
.mfb-select.has-val{border-color:var(--navy);color:var(--navy);font-weight:700}
.map-pin-circle.faded{
  background:#8899A6;border-color:#A0ADB8;
  opacity:0.45;animation:none;
  box-shadow:0 2px 8px rgba(0,30,46,0.2);
}
.map-pin-label-tag.faded{background:rgba(136,153,166,0.7);opacity:0.5}

/* ── Builder Showcase ── */
.builder-showcase{background:var(--navy-mid);padding:24px 28px}
.builder-showcase-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.builder-showcase-title{color:#fff;font-size:14px;font-weight:700;letter-spacing:-0.2px}
.builder-showcase-sub{color:rgba(203,210,216,0.6);font-size:12px;margin-top:2px}
.builder-showcase-scroll{
  display:flex;gap:14px;overflow-x:auto;padding-bottom:4px;
  scrollbar-width:thin;scrollbar-color:rgba(203,210,216,0.3) transparent;
}
.builder-showcase-scroll::-webkit-scrollbar{height:4px}
.builder-showcase-scroll::-webkit-scrollbar-track{background:transparent}
.builder-showcase-scroll::-webkit-scrollbar-thumb{background:rgba(203,210,216,0.3);border-radius:2px}
.bs-card{
  flex-shrink:0;width:200px;background:rgba(255,255,255,0.06);
  border:1px solid rgba(255,255,255,0.1);border-radius:var(--radius-lg);
  padding:18px 16px;cursor:pointer;transition:all 0.2s ease;
}
.bs-card:hover{background:rgba(255,255,255,0.12);border-color:var(--accent);transform:translateY(-2px)}
.bs-card-logo{
  width:46px;height:46px;border-radius:12px;
  display:flex;align-items:center;justify-content:center;
  font-size:16px;font-weight:900;color:#fff;margin-bottom:12px;letter-spacing:-0.5px;
}
.bs-card-name{font-size:13px;font-weight:800;color:#fff;margin-bottom:4px}
.bs-card-tier{
  display:inline-block;padding:3px 8px;border-radius:20px;
  font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;
  margin-bottom:10px;
}
.bs-card-tier.entry{background:rgba(16,185,129,0.2);color:#6EE7B7}
.bs-card-tier.entry-mid{background:rgba(59,130,246,0.2);color:#93C5FD}
.bs-card-tier.mid{background:rgba(139,92,246,0.2);color:#C4B5FD}
.bs-card-tier.mid-premium{background:rgba(236,72,153,0.2);color:#F9A8D4}
.bs-card-tier.premium{background:rgba(245,158,11,0.2);color:#FCD34D}
.bs-card-detail{font-size:10px;color:rgba(203,210,216,0.7);display:flex;justify-content:space-between;margin-top:4px}
.bs-card-detail span:last-child{color:rgba(203,210,216,0.5)}
.bs-card-cta{margin-top:12px;width:100%;padding:8px;background:rgba(0,163,224,0.2);color:var(--accent);border:1px solid rgba(0,163,224,0.3);border-radius:var(--radius-sm);font-size:11px;font-weight:700;transition:all var(--transition);text-align:center}
.bs-card:hover .bs-card-cta{background:var(--accent);color:#fff;border-color:var(--accent)}

/* ── Entry Path Cards ── */
.entry-paths{background:var(--bg);padding:28px}
.entry-paths-title{text-align:center;font-size:13px;font-weight:600;color:var(--text-light);text-transform:uppercase;letter-spacing:1px;margin-bottom:20px}
.entry-paths-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:760px;margin:0 auto}
.entry-path-card{
  background:#fff;border-radius:var(--radius-lg);padding:28px 24px;
  box-shadow:var(--shadow-sm);border:2px solid transparent;
  cursor:pointer;transition:all 0.2s ease;display:flex;flex-direction:column;align-items:flex-start;
}
.entry-path-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-3px);border-color:var(--accent)}
.entry-path-icon{
  width:52px;height:52px;border-radius:14px;
  display:flex;align-items:center;justify-content:center;
  font-size:24px;margin-bottom:16px;
}
.entry-path-icon.land{background:linear-gradient(135deg,#001E2E,#003855)}
.entry-path-icon.builder{background:linear-gradient(135deg,#0082B3,#00A3E0)}
.entry-path-title{font-size:17px;font-weight:800;color:var(--navy);margin-bottom:6px}
.entry-path-desc{font-size:12px;color:var(--text-light);line-height:1.6;margin-bottom:16px;flex:1}
.entry-path-steps{display:flex;flex-direction:column;gap:5px;margin-bottom:18px}
.entry-path-step{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--text-mid)}
.entry-path-step-dot{width:18px;height:18px;border-radius:50%;background:var(--silver-xlight);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:var(--text-light);flex-shrink:0}
.entry-path-card:hover .entry-path-step-dot{background:var(--accent);color:#fff}
.entry-path-btn{
  width:100%;padding:12px;border:none;border-radius:var(--radius-sm);
  font-size:13px;font-weight:700;letter-spacing:0.3px;transition:all var(--transition);
}
.entry-path-card.land-card .entry-path-btn{background:var(--navy);color:#fff}
.entry-path-card.land-card:hover .entry-path-btn{background:var(--accent)}
.entry-path-card.builder-card .entry-path-btn{background:var(--accent);color:#fff}
.entry-path-card.builder-card:hover .entry-path-btn{background:var(--accent-dark)}

/* ── View Content Wrapper ── */
.view-content{flex:1;padding:28px;max-width:1200px;margin:0 auto;width:100%}
.view-content.full{max-width:none;padding:0}

/* ── Section Headers ── */
.view-header{margin-bottom:24px}
.view-header h2{font-size:24px;font-weight:800;color:var(--navy);letter-spacing:-0.5px;margin-bottom:6px}
.view-header p{font-size:13px;color:var(--text-light)}
.view-header-row{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}
.back-btn{
  display:flex;align-items:center;gap:6px;
  background:#fff;border:2px solid var(--silver-light);color:var(--text-mid);
  padding:9px 18px;border-radius:var(--radius-sm);font-size:12px;font-weight:700;
  transition:all var(--transition);white-space:nowrap;flex-shrink:0;margin-bottom:16px;
}
.back-btn:hover{border-color:var(--navy);color:var(--navy)}

/* ── Lot Filter Controls ── */
.filter-bar{
  background:#fff;border-radius:var(--radius);padding:14px 18px;
  box-shadow:var(--shadow-sm);margin-bottom:20px;
  display:flex;align-items:center;gap:12px;flex-wrap:wrap;
}
.filter-bar select{
  padding:9px 12px;border:2px solid var(--silver-light);border-radius:var(--radius-sm);
  font-size:12px;font-weight:600;color:var(--navy);outline:none;
  transition:border-color var(--transition);background:#fff;
}
.filter-bar select:focus{border-color:var(--accent)}
.filter-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-xlight);display:block;margin-bottom:3px}
.filter-group{display:flex;flex-direction:column}
.filter-result-count{font-size:12px;color:var(--text-xlight);margin-left:auto}
.filter-chip{padding:7px 14px;border-radius:20px;border:2px solid var(--silver-light);font-size:11px;font-weight:600;color:var(--text-mid);cursor:pointer;transition:all var(--transition);background:#fff}
.filter-chip.active{border-color:var(--navy);background:var(--navy);color:#fff}
.filter-chip:hover:not(.active){border-color:var(--accent);color:var(--accent)}

/* ── Lot Grid ── */
.lot-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.lot-card{background:#fff;border-radius:var(--radius);padding:20px;box-shadow:var(--shadow-sm);border:2px solid transparent;transition:all 0.2s ease;cursor:pointer}
.lot-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px)}
.lot-card.selected{border-color:var(--accent);background:linear-gradient(135deg,#fff 0%,#f0f9ff 100%)}
.lot-card-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px}
.lot-name{font-size:18px;font-weight:800;color:var(--navy)}
.lot-stage{font-size:10px;font-weight:600;color:var(--text-xlight);margin-top:2px}
.lot-avail{padding:4px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.3px}
.lot-avail.Available{background:#D1FAE5;color:#065F46}
.lot-avail.Reserved{background:#E0E7FF;color:#3730A3}
.lot-avail.Unreleased{background:#F3F4F6;color:#6B7280}
.lot-specs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.lot-spec{padding:8px 10px;background:var(--silver-xlight);border-radius:var(--radius-sm);text-align:center}
.lot-spec .sv{font-size:16px;font-weight:800;color:var(--navy)}
.lot-spec .sl{font-size:9px;font-weight:600;color:var(--text-xlight);text-transform:uppercase;letter-spacing:0.3px}
.lot-price-row{display:flex;align-items:center;justify-content:space-between}
.lot-price{font-size:20px;font-weight:800;color:var(--accent)}
.lot-select-btn{background:var(--navy);color:#fff;border:none;padding:9px 16px;border-radius:var(--radius-sm);font-size:11px;font-weight:700;letter-spacing:0.3px;text-transform:uppercase;transition:background var(--transition)}
.lot-card.selected .lot-select-btn{background:var(--accent)}
.lot-select-btn:hover{background:var(--accent)}
.no-results{grid-column:1/-1;text-align:center;padding:52px 20px;color:var(--text-xlight);font-size:14px}
.no-results .icon{font-size:42px;margin-bottom:10px}

/* ── Builder Grid (Select for Lot) ── */
.builder-select-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:18px}
.builder-select-card{
  background:#fff;border-radius:var(--radius-lg);padding:22px;
  box-shadow:var(--shadow-sm);border:2px solid transparent;
  transition:all 0.2s ease;cursor:pointer;position:relative;
}
.builder-select-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px)}
.builder-select-card.selected{border-color:var(--accent);background:linear-gradient(135deg,#fff 0%,#f0f9ff 100%)}
.builder-select-card.maxed{opacity:0.45;cursor:not-allowed;pointer-events:none}
.bsc-check{position:absolute;top:14px;right:14px;width:26px;height:26px;border:2px solid var(--silver);border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;transition:all var(--transition)}
.builder-select-card.selected .bsc-check{background:var(--accent);border-color:var(--accent)}
.bsc-logo{width:50px;height:50px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;color:#fff;margin-bottom:14px}
.bsc-name{font-size:16px;font-weight:800;color:var(--navy);margin-bottom:2px}
.bsc-tagline{font-size:11px;color:var(--text-light);margin-bottom:12px}
.bsc-attrs{display:flex;flex-direction:column;gap:6px}
.bsc-attr{display:flex;align-items:center;gap:8px;font-size:11px}
.bsc-attr-icon{width:24px;height:24px;background:var(--silver-xlight);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
.bsc-attr-lbl{color:var(--text-light)}
.bsc-attr-val{font-weight:700;color:var(--navy);margin-left:auto}
.bsc-tier{display:inline-block;margin-top:12px;padding:4px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px}
.tier-entry{background:#F0FDF4;color:#166534}
.tier-entry-mid{background:#EFF6FF;color:#1E40AF}
.tier-mid{background:#EEF2FF;color:#3730A3}
.tier-mid-premium{background:#FDF4FF;color:#6B21A8}
.tier-premium{background:#FFF7ED;color:#9A3412}
.builder-max-hint{
  text-align:center;padding:12px 16px;background:var(--silver-xlight);border-radius:var(--radius-sm);
  font-size:12px;color:var(--text-mid);margin-bottom:16px;
}
.builder-max-hint strong{color:var(--navy)}

/* ── Design Grid ── */
.design-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.design-card{background:#fff;border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow-sm);border:2px solid transparent;transition:all 0.2s ease;cursor:pointer}
.design-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-3px)}
.design-card.selected{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-glow),var(--shadow-md)}
.design-card.incompatible{opacity:0.45}
.design-thumb{height:175px;position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}
.design-thumb-bg{position:absolute;inset:0}
.design-thumb-icon{position:relative;z-index:1;font-size:60px;opacity:0.12}
.design-thumb-overlay{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-end;padding:14px;background:linear-gradient(to top,rgba(0,30,46,0.85) 0%,transparent 60%)}
.design-thumb-name{color:#fff;font-size:15px;font-weight:800;letter-spacing:-0.3px}
.design-thumb-builder{color:rgba(255,255,255,0.6);font-size:11px;font-weight:500;margin-top:2px}
.design-compat-badge{position:absolute;top:10px;right:10px;z-index:3;padding:4px 9px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.3px}
.design-compat-badge.fit{background:var(--green);color:#fff}
.design-compat-badge.tight{background:var(--amber);color:#fff}
.design-compat-badge.no{background:var(--red);color:#fff}
.design-body{padding:16px}
.design-specs{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.design-spec-pill{display:flex;align-items:center;gap:4px;background:var(--silver-xlight);padding:4px 9px;border-radius:20px;font-size:11px;font-weight:600;color:var(--text-mid)}
.design-footer{display:flex;align-items:flex-end;justify-content:space-between}
.design-price{font-size:16px;font-weight:800;color:var(--accent)}
.design-size{font-size:11px;color:var(--text-light)}
.design-frontage-req{font-size:10px;color:var(--text-xlight);margin-top:2px}
.design-select-btn{margin-top:12px;width:100%;padding:9px;background:var(--navy);color:#fff;border:none;border-radius:var(--radius-sm);font-size:11px;font-weight:700;letter-spacing:0.3px;text-transform:uppercase;transition:background var(--transition)}
.design-card.selected .design-select-btn{background:var(--accent)}
.design-select-btn:hover{background:var(--accent)}
.frontage-notice{padding:12px 16px;background:#FEF3C7;border-radius:var(--radius-sm);border-left:4px solid var(--amber);font-size:12px;color:#92400E;margin-bottom:16px}

/* ── Continue Footer ── */
.continue-footer{
  background:#fff;border-top:1px solid var(--silver-light);
  padding:18px 28px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;bottom:0;z-index:50;
}
.continue-footer-left{font-size:12px;color:var(--text-xlight)}
.continue-footer-left strong{color:var(--navy)}
.continue-btn{
  background:var(--navy);color:#fff;border:none;
  padding:13px 32px;border-radius:var(--radius-sm);font-size:13px;font-weight:700;
  letter-spacing:0.5px;transition:all var(--transition);
  display:flex;align-items:center;gap:8px;
}
.continue-btn:hover{background:var(--accent)}
.continue-btn:disabled{background:var(--silver-light);color:var(--text-xlight);cursor:not-allowed}
.continue-btn svg{transition:transform var(--transition)}
.continue-btn:hover:not(:disabled) svg{transform:translateX(3px)}
.validation-msg{
  background:#FEF2F2;border:1px solid #FECACA;border-radius:var(--radius-sm);
  padding:10px 14px;font-size:12px;color:var(--red);display:none;
}
.validation-msg.visible{display:block}

/* ── Customize View ── */
.customize-layout{display:grid;grid-template-columns:1fr 340px;gap:22px;align-items:start}
.customize-section{background:#fff;border-radius:var(--radius-lg);padding:22px;box-shadow:var(--shadow-sm);margin-bottom:18px}
.customize-section-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--navy);margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid var(--silver-xlight)}
.facade-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.facade-option{border:2px solid var(--silver-light);border-radius:var(--radius);padding:14px;cursor:pointer;transition:all var(--transition)}
.facade-option:hover{border-color:var(--accent)}
.facade-option.selected{border-color:var(--accent);background:var(--accent-glow)}
.facade-thumb{height:70px;border-radius:var(--radius-sm);margin-bottom:10px;display:flex;align-items:center;justify-content:center;font-size:24px;position:relative;overflow:hidden}
.facade-thumb-bg{position:absolute;inset:0}
.facade-thumb-icon{position:relative;z-index:1;opacity:0.45}
.facade-name{font-size:12px;font-weight:700;color:var(--navy)}
.facade-price{font-size:11px;color:var(--text-light);margin-top:2px}
.inclusions-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.incl-option{border:2px solid var(--silver-light);border-radius:var(--radius);padding:16px 12px;cursor:pointer;transition:all var(--transition);text-align:center}
.incl-option:hover{border-color:var(--accent)}
.incl-option.selected{border-color:var(--navy);background:var(--navy)}
.incl-option.selected .incl-name,.incl-option.selected .incl-price{color:#fff}
.incl-option.selected .incl-desc{color:rgba(255,255,255,0.65)}
.incl-name{font-size:14px;font-weight:800;color:var(--navy);margin-bottom:6px}
.incl-desc{font-size:10px;color:var(--text-light);margin-bottom:10px;line-height:1.4}
.incl-price{font-size:13px;font-weight:700;color:var(--accent)}
.upgrades-list{display:flex;flex-direction:column;gap:10px}
.upgrade-item{display:flex;align-items:center;gap:12px;padding:13px 14px;border:2px solid var(--silver-light);border-radius:var(--radius);cursor:pointer;transition:all var(--transition)}
.upgrade-item:hover{border-color:var(--accent)}
.upgrade-item.selected{border-color:var(--accent);background:var(--accent-glow)}
.upgrade-check{width:22px;height:22px;border:2px solid var(--silver);border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:all var(--transition)}
.upgrade-item.selected .upgrade-check{background:var(--accent);border-color:var(--accent)}
.upgrade-icon{font-size:20px;flex-shrink:0}
.upgrade-info{flex:1}
.upgrade-name{font-size:12px;font-weight:700;color:var(--navy)}
.upgrade-desc{font-size:11px;color:var(--text-light);margin-top:1px}
.upgrade-price{font-size:12px;font-weight:700;color:var(--accent);flex-shrink:0}

/* ── Pricing Sidebar ── */
.pricing-sidebar{background:var(--navy);border-radius:var(--radius-lg);padding:22px;color:#fff;position:sticky;top:76px}
.pricing-sidebar h3{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--silver);margin-bottom:16px}
.pricing-design-preview{padding:12px;background:rgba(255,255,255,0.06);border-radius:var(--radius-sm);margin-bottom:14px}
.pricing-design-name{font-size:13px;font-weight:700;color:#fff}
.pricing-design-sub{font-size:11px;color:var(--silver);margin-top:2px}
.pricing-rows{margin-bottom:14px}
.pricing-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.07)}
.pricing-row:last-child{border-bottom:none}
.pricing-row-lbl{font-size:11px;color:var(--silver)}
.pricing-row-val{font-size:12px;font-weight:700;color:#fff}
.pricing-total{margin-top:14px;padding:16px;background:rgba(0,163,224,0.15);border-radius:var(--radius);border:1px solid rgba(0,163,224,0.3);text-align:center}
.pricing-total .lbl{font-size:10px;font-weight:600;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px}
.pricing-total .amount{font-size:26px;font-weight:900;color:var(--accent);letter-spacing:-1px}
.pricing-total .qualifier{font-size:10px;color:rgba(255,255,255,0.35);margin-top:4px}
.pricing-disclaimer{margin-top:12px;font-size:10px;color:rgba(203,210,216,0.35);line-height:1.5}

/* ── Summary & EOI ── */
.summary-hero{
  background:linear-gradient(135deg,var(--navy) 0%,var(--navy-light) 100%);
  padding:28px;color:#fff;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;
}
.summary-hero-left .lbl{font-size:11px;font-weight:600;color:var(--silver);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px}
.summary-hero-left .amount{font-size:34px;font-weight:900;color:#fff;letter-spacing:-1.5px}
.summary-hero-left .qualifier{font-size:11px;color:rgba(255,255,255,0.45);margin-top:4px}
.summary-hero-right{text-align:right}
.summary-hero-right .proj-name{font-size:18px;font-weight:800;color:#fff}
.summary-hero-right .proj-sub{font-size:12px;color:var(--silver);margin-top:2px}
.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:28px;max-width:1200px;margin:0 auto;width:100%}
.summary-card{background:#fff;border-radius:var(--radius-lg);padding:22px;box-shadow:var(--shadow-sm)}
.summary-card h4{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-light);margin-bottom:14px}
.summary-row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--silver-xlight);font-size:12px}
.summary-row:last-child{border-bottom:none}
.summary-row .s-lbl{color:var(--text-light)}
.summary-row .s-val{font-weight:700;color:var(--navy)}
.eoi-section{background:#fff;border-radius:var(--radius-lg);padding:26px;box-shadow:var(--shadow-sm);margin:0 28px 28px}
.eoi-section h3{font-size:19px;font-weight:800;color:var(--navy);margin-bottom:4px}
.eoi-section .eoi-sub{font-size:13px;color:var(--text-light);margin-bottom:22px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.form-field{display:flex;flex-direction:column;gap:5px}
.form-field.full{grid-column:1/-1}
.form-field label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-mid)}
.form-field input,.form-field select,.form-field textarea{padding:11px 13px;border:2px solid var(--silver-light);border-radius:var(--radius-sm);font-size:14px;color:var(--navy);outline:none;transition:border-color var(--transition);background:#fff}
.form-field input:focus,.form-field select:focus,.form-field textarea:focus{border-color:var(--accent)}
.form-field textarea{resize:vertical;min-height:76px}
.eoi-disclaimer{padding:12px 14px;background:var(--silver-xlight);border-radius:var(--radius-sm);font-size:11px;color:var(--text-light);margin:14px 0;line-height:1.5}
.btn-submit{width:100%;padding:15px;background:var(--accent);color:#fff;border:none;border-radius:var(--radius);font-size:14px;font-weight:700;letter-spacing:0.5px;transition:all var(--transition)}
.btn-submit:hover{background:var(--accent-dark);transform:translateY(-1px)}
.success-state{text-align:center;padding:48px 20px;display:none}
.success-state.visible{display:block}
.eoi-form-inner.hidden{display:none}
.success-icon{font-size:52px;margin-bottom:14px}
.success-state h3{font-size:21px;font-weight:800;color:var(--navy);margin-bottom:8px}
.success-state p{font-size:13px;color:var(--text-light);max-width:400px;margin:0 auto}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--silver);border-radius:3px}

/* ── General: prevent horizontal overflow ── */
html,body{overflow-x:hidden;max-width:100vw}

/* ── Mobile: tablet ── */
@media(max-width:900px){
  body{font-size:15px}
  .customize-layout{grid-template-columns:1fr}
  .pricing-sidebar{position:static}
  .entry-paths-grid{grid-template-columns:1fr}
  .summary-grid{grid-template-columns:1fr}
  .summary-hero{flex-direction:column}
  .summary-hero-right{text-align:left}
  .form-grid{grid-template-columns:1fr}
  .inclusions-grid{grid-template-columns:1fr 1fr}
  .builder-select-grid{grid-template-columns:1fr 1fr}
  .design-grid{grid-template-columns:1fr 1fr}
  .lot-grid{grid-template-columns:1fr 1fr}
}

/* ── Mobile: phone ── */
@media(max-width:640px){
  body{font-size:14px;-webkit-text-size-adjust:100%}

  /* Map: full viewport height, larger targets */
  #map{height:calc(100vh - 60px);min-height:300px}
  .map-overlay-header{
    top:12px;padding:10px 16px;border-radius:12px;
    max-width:calc(100vw - 32px);white-space:normal;
  }
  .map-overlay-header h1{font-size:15px}
  .map-overlay-header p{font-size:11px}
  .map-entry-btns{
    flex-direction:column;gap:8px;align-items:stretch;
    bottom:12px;left:12px;right:12px;transform:none;width:auto;
  }
  .map-entry-btn{
    padding:14px 18px;font-size:14px;justify-content:center;
    min-height:48px;border-radius:12px;
  }
  .map-pin-circle{width:48px;height:48px}
  .map-pin-count{font-size:15px}
  .map-pin-label-tag{font-size:10px;padding:4px 8px}

  /* Map filter bar: stacked on mobile */
  .map-filter-bar{padding:8px 12px;gap:8px}
  .mfb-group{width:100%}
  .mfb-chips{gap:6px}
  .mfb-chip{padding:9px 14px;font-size:12px;min-height:44px;display:inline-flex;align-items:center}
  .mfb-select{padding:10px 14px;font-size:13px;min-height:44px;width:100%;border-radius:10px}
  .mfb-clear{padding:10px 12px;font-size:12px;min-height:44px;width:100%;text-align:center}

  /* Leaflet popups: readable on mobile */
  .leaflet-popup-content{width:calc(100vw - 60px) !important;max-width:300px !important;min-width:200px !important}
  .popup-inner{padding:14px}
  .popup-project-name{font-size:16px}
  .popup-suburb{font-size:12px}
  .popup-stat-val{font-size:15px}
  .popup-stat-lbl{font-size:10px}
  .popup-btn{padding:12px;font-size:14px;min-height:48px}

  /* Top bar */
  .top-bar{padding:0 12px;height:54px}
  .top-bar-left{gap:8px}
  .top-logo{font-size:12px;padding:5px 10px}
  .top-title{font-size:12px}
  .top-title span{font-size:10px}
  .confidential-badge{font-size:9px;padding:3px 8px}
  .top-home-btn{font-size:12px;padding:8px 14px;min-height:44px}

  /* Breadcrumb → Back button on mobile */
  .breadcrumb-bar{padding:8px 12px;min-height:auto}
  .breadcrumb{gap:4px}
  .bc-item{font-size:11px}
  .bc-sep{font-size:10px}
  /* Hide middle breadcrumb items on small screens, show first and last */
  .breadcrumb .bc-item:not(:first-child):not(:last-child):not(.current){display:none}
  .breadcrumb .bc-sep:not(:first-of-type):not(:last-of-type){display:none}

  /* View content */
  .view-content{padding:12px}
  .view-header h2{font-size:20px}
  .view-header p{font-size:12px}
  .back-btn{padding:10px 14px;font-size:12px;min-height:44px;margin-bottom:12px}

  /* Cards/grids: single column, no overflow */
  .lot-grid{grid-template-columns:1fr;gap:12px}
  .builder-select-grid{grid-template-columns:1fr;gap:12px}
  .design-grid{grid-template-columns:1fr;gap:14px}
  .inclusions-grid{grid-template-columns:1fr}

  /* Lot cards */
  .lot-card{padding:16px}
  .lot-name{font-size:16px}
  .lot-price{font-size:18px}
  .lot-select-btn{padding:10px 16px;font-size:12px;min-height:44px}
  .lot-spec .sv{font-size:15px}

  /* Builder select cards */
  .builder-select-card{padding:18px}
  .bsc-name{font-size:15px}
  .bsc-attr{font-size:12px;min-height:36px}

  /* Design cards */
  .design-card{border-radius:12px}
  .design-thumb{height:150px}
  .design-thumb-name{font-size:14px}
  .design-select-btn{padding:12px;font-size:12px;min-height:44px}
  .design-price{font-size:15px}

  /* Builder showcase: vertical scroll on mobile */
  .builder-showcase{padding:16px 12px}
  .builder-showcase-title{font-size:13px}
  .builder-showcase-sub{font-size:11px}
  .builder-showcase-scroll{
    flex-direction:column;overflow-x:visible;overflow-y:auto;
    max-height:none;gap:10px;padding-bottom:0;
  }
  .bs-card{
    width:100%;flex-shrink:1;
    display:flex;align-items:center;gap:14px;
    padding:14px;
  }
  .bs-card-logo{width:42px;height:42px;margin-bottom:0;flex-shrink:0;font-size:14px}
  .bs-card-name{font-size:13px;margin-bottom:2px}
  .bs-card-tier{margin-bottom:4px}
  .bs-card-detail{font-size:10px}
  .bs-card-cta{margin-top:8px;padding:8px;min-height:40px;font-size:12px}

  /* Entry paths */
  .entry-paths{padding:16px 12px}
  .entry-paths-grid{grid-template-columns:1fr;gap:12px}
  .entry-path-card{padding:20px 16px}
  .entry-path-title{font-size:16px}
  .entry-path-desc{font-size:12px}
  .entry-path-btn{padding:14px;font-size:13px;min-height:48px}
  .entry-path-icon{width:44px;height:44px;font-size:20px}

  /* Filters: collapsible on mobile */
  .filter-bar{
    padding:12px;gap:8px;flex-direction:column;align-items:stretch;
    position:relative;
  }
  .filter-bar select{
    width:100%;padding:12px;font-size:14px;min-height:44px;
    border-radius:8px;
  }
  .filter-group{width:100%}
  .filter-label{font-size:11px;margin-bottom:4px}
  .filter-result-count{margin-left:0;text-align:center;font-size:12px;padding-top:4px}
  .filter-chip{
    padding:10px 16px;font-size:12px;min-height:44px;
    display:inline-flex;align-items:center;justify-content:center;
  }

  /* Forms: full-width, min 44px tap targets */
  .form-grid{grid-template-columns:1fr;gap:12px}
  .form-field input,.form-field select,.form-field textarea{
    padding:13px;font-size:16px;min-height:48px;border-radius:10px;
  }
  .form-field label{font-size:11px}
  .btn-submit{padding:16px;font-size:15px;min-height:52px;border-radius:12px}
  .eoi-section{margin:0 12px 12px;padding:20px 16px}
  .eoi-section h3{font-size:17px}
  .eoi-section .eoi-sub{font-size:12px}
  .eoi-disclaimer{font-size:10px;padding:10px 12px}

  /* Customize: horizontal scroll facades, full-width upgrades */
  .customize-layout{grid-template-columns:1fr;gap:14px}
  .customize-section{padding:16px;margin-bottom:12px}
  .customize-section-title{font-size:11px;margin-bottom:12px}
  .facade-grid{
    grid-template-columns:none;display:flex;
    overflow-x:auto;gap:10px;padding-bottom:8px;
    scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;
  }
  .facade-option{
    min-width:140px;flex-shrink:0;scroll-snap-align:start;
    padding:12px;
  }
  .facade-option:hover{border-color:var(--accent)}
  .facade-thumb{height:60px}
  .facade-name{font-size:12px}
  .facade-price{font-size:11px}
  .incl-option{padding:14px 10px}
  .incl-name{font-size:13px}
  .incl-desc{font-size:10px}
  .incl-price{font-size:12px}
  .upgrade-item{padding:12px;gap:10px;min-height:56px}
  .upgrade-name{font-size:12px}
  .upgrade-desc{font-size:10px}
  .upgrade-price{font-size:12px}
  .upgrade-check{width:24px;height:24px}

  /* Pricing sidebar: sticky price bar on mobile */
  .pricing-sidebar{
    position:sticky;bottom:64px;z-index:40;
    border-radius:12px;padding:16px;margin-top:4px;
  }
  .pricing-sidebar h3{font-size:11px;margin-bottom:12px}
  .pricing-total .amount{font-size:22px}
  .pricing-row{padding:6px 0}
  .pricing-row-lbl{font-size:10px}
  .pricing-row-val{font-size:11px}

  /* Continue footer: sticky bottom nav buttons */
  .continue-footer{
    padding:12px;position:sticky;bottom:0;z-index:50;
    flex-direction:column;gap:8px;align-items:stretch;
  }
  .continue-footer-left{font-size:11px;text-align:center}
  .continue-btn{
    width:100%;padding:14px 20px;font-size:14px;
    min-height:52px;justify-content:center;border-radius:10px;
  }

  /* Summary */
  .summary-hero{padding:16px 12px;flex-direction:column;gap:12px}
  .summary-hero-left .amount{font-size:26px}
  .summary-hero-left .lbl{font-size:10px}
  .summary-hero-right{text-align:left}
  .summary-hero-right .proj-name{font-size:16px}
  .summary-grid{padding:12px;gap:12px;grid-template-columns:1fr}
  .summary-card{padding:16px}
  .summary-card h4{font-size:10px}
  .summary-row{font-size:11px}

  /* Success state */
  .success-state{padding:32px 16px}
  .success-icon{font-size:44px}
  .success-state h3{font-size:18px}
  .success-state p{font-size:12px}

  /* Password gate */
  .gate-box{padding:28px 20px;border-radius:20px}
  .gate-box h2{font-size:18px}
  .gate-input{padding:14px;font-size:16px;min-height:48px}
  .gate-btn{padding:14px;min-height:48px;font-size:12px}
  .gate-badge{font-size:9px}
  .gate-footer{font-size:10px}

  /* Validation messages */
  .validation-msg{font-size:12px;padding:10px 12px}
  .builder-max-hint{font-size:11px;padding:10px 12px}
  .frontage-notice{font-size:11px;padding:10px 12px}
}

/* ── Extra small: 375px and below ── */
@media(max-width:375px){
  .top-bar{height:50px}
  .top-title span{display:none}
  .confidential-badge{display:none}
  .map-overlay-header{display:none}
  #map{height:calc(100vh - 50px)}
  .map-entry-btns{bottom:8px;left:8px;right:8px;gap:6px}
  .map-entry-btn{padding:12px 14px;font-size:13px;min-height:44px}
  .view-content{padding:10px}
  .lot-card{padding:14px}
  .lot-name{font-size:15px}
  .lot-price{font-size:16px}
  .entry-path-card{padding:16px 14px}
  .entry-path-title{font-size:15px}
  .facade-option{min-width:120px}
  .summary-hero-left .amount{font-size:22px}
  .eoi-section{margin:0 10px 10px;padding:16px 12px}
  .bs-card{padding:12px;gap:10px}
  .map-filter-bar{padding:6px 8px;gap:6px}
  .mfb-chip{padding:8px 12px;font-size:11px;min-height:40px}
  .mfb-label{font-size:8px}
}
</style>
</head>
<body>

<!-- ── Password Gate ── -->
<div id="auth-gate">
  <div class="gate-wrap">
    <div class="gate-logo">PX</div>
    <div class="gate-box">
      <div class="gate-badge">⚠ Confidential — Consultant Access Only</div>
      <h2>House &amp; Land Design Portal</h2>
      <p class="gate-sub">Enter your access code to continue</p>
      <input type="password" id="gate-pass" class="gate-input" placeholder="Access Code" autocomplete="off"/>
      <button class="gate-btn" onclick="checkAccess()">Access Portal</button>
    </div>
    <div class="gate-footer">ProjX Australia &mdash; Confidential &amp; Not For Distribution</div>
  </div>
</div>

<!-- ── App ── -->
<div id="app">

  <!-- Top Bar -->
  <div class="top-bar">
    <div class="top-bar-left">
      <div class="top-logo" onclick="goHome()">PX</div>
      <div>
        <div class="top-title">House &amp; Land Design Portal <span>— V2.3</span></div>
      </div>
    </div>
    <div class="top-bar-right">
      <button class="top-home-btn" id="top-home-btn" onclick="goHome()">← Back to Map</button>
      <div class="confidential-badge">⚠ Consultant Only</div>
    </div>
  </div>

  <!-- Breadcrumb -->
  <div class="breadcrumb-bar">
    <div class="breadcrumb" id="breadcrumb">
      <span class="bc-item current">Home</span>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: LANDING                                  -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view active" id="view-landing" style="flex-direction:column">

    <!-- Map Filter Bar -->
    <div class="map-filter-bar" id="map-filter-bar">
      <div class="mfb-group">
        <span class="mfb-label">Package Price</span>
        <select class="mfb-select" id="mf-price" onchange="applyMapFilters()">
          <option value="any">Any Price</option>
          <option value="0-450">&lt; $450k</option>
          <option value="450-550">$450k – $550k</option>
          <option value="550-650">$550k – $650k</option>
          <option value="650-750">$650k – $750k</option>
          <option value="750-up">$750k+</option>
        </select>
      </div>
      <div class="mfb-group">
        <span class="mfb-label">Bedrooms</span>
        <div class="mfb-chips">
          <button class="mfb-chip active" data-filter="mf-beds" data-val="any" onclick="setMapChip(this)">Any</button>
          <button class="mfb-chip" data-filter="mf-beds" data-val="3" onclick="setMapChip(this)">3</button>
          <button class="mfb-chip" data-filter="mf-beds" data-val="4" onclick="setMapChip(this)">4</button>
          <button class="mfb-chip" data-filter="mf-beds" data-val="5" onclick="setMapChip(this)">5+</button>
        </div>
      </div>
      <div class="mfb-group">
        <span class="mfb-label">Region</span>
        <div class="mfb-chips" style="overflow-x:auto;flex-wrap:nowrap;-webkit-overflow-scrolling:touch">
          <button class="mfb-chip active" data-filter="mf-region" data-val="all" onclick="setMapChip(this)">All Regions</button>
          __REGION_CHIPS__
        </div>
      </div>
      <div class="mfb-group">
        <span class="mfb-label">Timeline</span>
        <div class="mfb-chips">
          <button class="mfb-chip active" data-filter="mf-timeline" data-val="all" onclick="setMapChip(this)">All</button>
          <button class="mfb-chip" data-filter="mf-timeline" data-val="ready" onclick="setMapChip(this)">Ready Now</button>
          <button class="mfb-chip" data-filter="mf-timeline" data-val="coming" onclick="setMapChip(this)">Coming Soon</button>
        </div>
      </div>
      <button class="mfb-clear" id="mfb-clear" onclick="clearMapFilters()" style="display:none">✕ Clear All</button>
    </div>

    <!-- Map Hero -->
    <div class="map-section">
      <div id="map"></div>
      <div class="map-overlay-header">
        <h1>ProjX Project Locations</h1>
        <p>Click a pin to explore lots &amp; packages</p>
      </div>
      <div class="map-entry-btns">
        <button class="map-entry-btn primary" onclick="scrollToBuilders()">
          <svg width="16" height="16" fill="none" viewBox="0 0 16 16"><path d="M3 12L8 4l5 8H3z" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>
          Find a Builder First
        </button>
        <button class="map-entry-btn secondary" onclick="scrollToEntryPaths()">
          <svg width="16" height="16" fill="none" viewBox="0 0 16 16"><rect x="2" y="2" width="5" height="5" rx="1" stroke="#001E2E" stroke-width="1.5"/><rect x="9" y="2" width="5" height="5" rx="1" stroke="#001E2E" stroke-width="1.5"/><rect x="2" y="9" width="5" height="5" rx="1" stroke="#001E2E" stroke-width="1.5"/><rect x="9" y="9" width="5" height="5" rx="1" stroke="#001E2E" stroke-width="1.5"/></svg>
          How It Works
        </button>
      </div>
    </div>

    <!-- Builder Showcase -->
    <div class="builder-showcase" id="builder-showcase">
      <div class="builder-showcase-header">
        <div>
          <div class="builder-showcase-title">Partner Builders</div>
          <div class="builder-showcase-sub">Scroll to explore all ProjX builder partners</div>
        </div>
      </div>
      <div class="builder-showcase-scroll" id="builder-showcase-scroll"></div>
    </div>

    <!-- Entry Paths -->
    <div class="entry-paths" id="entry-paths">
      <div class="entry-paths-title">Choose your path</div>
      <div class="entry-paths-grid">
        <div class="entry-path-card land-card" onclick="startLandFirst()">
          <div class="entry-path-icon land">🗺️</div>
          <div class="entry-path-title">Find Land First</div>
          <div class="entry-path-desc">Explore a project, pick your ideal lot, then see which builders and designs suit your frontage.</div>
          <div class="entry-path-steps">
            <div class="entry-path-step"><div class="entry-path-step-dot">1</div>Pick a project on the map</div>
            <div class="entry-path-step"><div class="entry-path-step-dot">2</div>Select your lot</div>
            <div class="entry-path-step"><div class="entry-path-step-dot">3</div>Choose builder &amp; design</div>
            <div class="entry-path-step"><div class="entry-path-step-dot">4</div>Customise &amp; submit EOI</div>
          </div>
          <button class="entry-path-btn">Explore Projects on Map →</button>
        </div>
        <div class="entry-path-card builder-card" onclick="startBuilderFirst()">
          <div class="entry-path-icon builder">🏗️</div>
          <div class="entry-path-title">Find a Builder First</div>
          <div class="entry-path-desc">Browse builder designs first, then find which projects have lots that match your chosen home.</div>
          <div class="entry-path-steps">
            <div class="entry-path-step"><div class="entry-path-step-dot">1</div>Pick a builder above</div>
            <div class="entry-path-step"><div class="entry-path-step-dot">2</div>Browse their designs</div>
            <div class="entry-path-step"><div class="entry-path-step-dot">3</div>Find matching lots</div>
            <div class="entry-path-step"><div class="entry-path-step-dot">4</div>Customise &amp; submit EOI</div>
          </div>
          <button class="entry-path-btn">Browse Builder Designs →</button>
        </div>
      </div>
    </div>

  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: LOTS (Land First)                        -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-lots" style="flex-direction:column">
    <div class="view-content" style="flex:1">
      <button class="back-btn" onclick="goHome()">← Back to Map</button>
      <div class="view-header-row">
        <div class="view-header">
          <h2 id="lots-header-title">Available Lots</h2>
          <p id="lots-header-sub">Browse and select a lot to continue</p>
        </div>
      </div>
      <div class="filter-bar">
        <div class="filter-group">
          <span class="filter-label">Sort By</span>
          <select id="lot-sort" onchange="renderLots()">
            <option value="price-asc">Price: Low → High</option>
            <option value="price-desc">Price: High → Low</option>
            <option value="size-asc">Size: Small → Large</option>
            <option value="size-desc">Size: Large → Small</option>
          </select>
        </div>
        <div class="filter-group">
          <span class="filter-label">Status</span>
          <select id="lot-status" onchange="renderLots()">
            <option value="all">All Lots</option>
            <option value="Available">Available Only</option>
            <option value="Unreleased">Unreleased Only</option>
          </select>
        </div>
        <div class="filter-group">
          <span class="filter-label">Max Price</span>
          <select id="lot-max-price" onchange="renderLots()">
            <option value="0">Any Price</option>
            <option value="200000">Under $200k</option>
            <option value="250000">Under $250k</option>
            <option value="300000">Under $300k</option>
            <option value="350000">Under $350k</option>
            <option value="400000">Under $400k</option>
            <option value="450000">Under $450k</option>
            <option value="500000">Under $500k</option>
          </select>
        </div>
        <span class="filter-result-count" id="lot-count-label"></span>
      </div>
      <div class="validation-msg" id="err-lots">Please select a lot to continue.</div>
      <div class="lot-grid" id="lot-grid"></div>
    </div>
    <div class="continue-footer">
      <div class="continue-footer-left" id="lots-footer-info">Select a lot to continue</div>
      <button class="continue-btn" id="lots-continue-btn" onclick="continueFromLots()">
        Continue <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: BUILDER SELECT (after lot)               -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-lot-builders" style="flex-direction:column">
    <div class="view-content" style="flex:1">
      <button class="back-btn" onclick="showView('lots')">← Back to Lots</button>
      <div class="view-header">
        <h2>Choose Your Builder(s)</h2>
        <p id="lot-builders-sub">Select up to 2 ProjX partner builders to browse designs from.</p>
      </div>
      <div class="builder-max-hint">Select up to <strong>2 builders</strong> — you'll browse their designs next</div>
      <div class="validation-msg" id="err-builders">Please select at least one builder to continue.</div>
      <div class="builder-select-grid" id="builder-select-grid"></div>
    </div>
    <div class="continue-footer">
      <div class="continue-footer-left" id="builders-footer-info">0/2 builders selected</div>
      <button class="continue-btn" id="builders-continue-btn" onclick="continueFromBuilders()">
        Browse Designs <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: DESIGNS (after lot + builders)           -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-lot-designs" style="flex-direction:column">
    <div class="view-content" style="flex:1">
      <button class="back-btn" onclick="showView('lot-builders')">← Back to Builders</button>
      <div class="view-header">
        <h2>Browse Home Designs</h2>
        <p>Designs are filtered to match your lot frontage. Select a design to customise.</p>
      </div>
      <div class="frontage-notice" id="lot-designs-notice" style="display:none"></div>
      <div class="filter-bar">
        <button class="filter-chip active" onclick="filterDesigns('all',this,'lot-designs-grid')">All</button>
        <button class="filter-chip" onclick="filterDesigns('compatible',this,'lot-designs-grid')">Fits My Lot</button>
        <button class="filter-chip" onclick="filterDesigns('4bed',this,'lot-designs-grid')">4+ Bed</button>
        <button class="filter-chip" onclick="filterDesigns('5bed',this,'lot-designs-grid')">5 Bed</button>
        <span class="filter-result-count" id="lot-designs-count"></span>
      </div>
      <div class="validation-msg" id="err-lot-designs">Please select a design to continue.</div>
      <div class="design-grid" id="lot-designs-grid"></div>
    </div>
    <div class="continue-footer">
      <div class="continue-footer-left" id="lot-designs-footer-info">Select a design to continue</div>
      <button class="continue-btn" id="lot-designs-continue-btn" onclick="continueFromLotDesigns()">
        Customise <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: BUILDER BROWSE (Builder First)           -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-builder-browse" style="flex-direction:column">
    <div class="view-content" style="flex:1">
      <button class="back-btn" onclick="goHome()">← Back to Builders</button>
      <div class="view-header">
        <h2 id="builder-browse-title">Designs by Builder</h2>
        <p id="builder-browse-sub">Browse all available designs. Select one to find matching lots.</p>
      </div>
      <div class="filter-bar">
        <button class="filter-chip active" onclick="filterDesigns('all',this,'builder-designs-grid')">All Designs</button>
        <button class="filter-chip" onclick="filterDesigns('4bed',this,'builder-designs-grid')">4+ Bed</button>
        <button class="filter-chip" onclick="filterDesigns('5bed',this,'builder-designs-grid')">5 Bed</button>
        <span class="filter-result-count" id="builder-designs-count"></span>
      </div>
      <div class="validation-msg" id="err-builder-designs">Please select a design to continue.</div>
      <div class="design-grid" id="builder-designs-grid"></div>
    </div>
    <div class="continue-footer">
      <div class="continue-footer-left" id="builder-designs-footer-info">Select a design to find matching lots</div>
      <button class="continue-btn" id="builder-designs-continue-btn" onclick="continueFromBuilderDesigns()">
        Find Matching Lots <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: DESIGN → LOTS (Builder First)            -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-design-lots" style="flex-direction:column">
    <div class="view-content" style="flex:1">
      <button class="back-btn" onclick="showView('builder-browse')">← Back to Designs</button>
      <div class="view-header">
        <h2>Matching Lots</h2>
        <p id="design-lots-sub">These lots have the frontage required for your chosen design. Pick one to proceed.</p>
      </div>
      <div class="filter-bar">
        <div class="filter-group">
          <span class="filter-label">Project</span>
          <select id="design-lots-project-filter" onchange="renderDesignLots()">
            <option value="all">All Projects</option>
          </select>
        </div>
        <div class="filter-group">
          <span class="filter-label">Status</span>
          <select id="design-lots-status" onchange="renderDesignLots()">
            <option value="all">All</option>
            <option value="Available">Available Only</option>
            <option value="Unreleased">Unreleased Only</option>
          </select>
        </div>
        <span class="filter-result-count" id="design-lots-count"></span>
      </div>
      <div class="validation-msg" id="err-design-lots">Please select a lot to continue.</div>
      <div class="lot-grid" id="design-lots-grid"></div>
    </div>
    <div class="continue-footer">
      <div class="continue-footer-left" id="design-lots-footer-info">Select a lot to continue</div>
      <button class="continue-btn" id="design-lots-continue-btn" onclick="continueFromDesignLots()">
        Customise <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: CUSTOMIZE                                -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-customize" style="flex-direction:column">
    <div class="view-content" style="flex:1">
      <button class="back-btn" id="customize-back-btn" onclick="goBackFromCustomize()">← Back</button>
      <div class="view-header">
        <h2>Customise Your Home</h2>
        <p>Choose your facade, inclusions package, and optional upgrades.</p>
      </div>
      <div class="customize-layout">
        <div class="customize-main">
          <div class="customize-section">
            <div class="customize-section-title">Facade Selection</div>
            <div class="facade-grid" id="facade-grid"></div>
          </div>
          <div class="customize-section">
            <div class="customize-section-title">Inclusions Package</div>
            <div class="inclusions-grid" id="inclusions-grid"></div>
          </div>
          <div class="customize-section">
            <div class="customize-section-title">Optional Upgrades</div>
            <div class="upgrades-list" id="upgrades-list"></div>
          </div>
        </div>
        <div class="pricing-sidebar">
          <h3>Indicative Pricing</h3>
          <div class="pricing-design-preview" id="pricing-preview"></div>
          <div class="pricing-rows">
            <div class="pricing-row"><span class="pricing-row-lbl">Land</span><span class="pricing-row-val" id="price-land">—</span></div>
            <div class="pricing-row"><span class="pricing-row-lbl">Build (Base)</span><span class="pricing-row-val" id="price-build">—</span></div>
            <div class="pricing-row"><span class="pricing-row-lbl">Facade</span><span class="pricing-row-val" id="price-facade">Included</span></div>
            <div class="pricing-row"><span class="pricing-row-lbl">Inclusions</span><span class="pricing-row-val" id="price-inclusions">Standard</span></div>
            <div class="pricing-row"><span class="pricing-row-lbl">Upgrades</span><span class="pricing-row-val" id="price-upgrades">$0</span></div>
          </div>
          <div class="pricing-total">
            <div class="lbl">Total Package From</div>
            <div class="amount" id="price-total">—</div>
            <div class="qualifier">Indicative only</div>
          </div>
          <div class="pricing-disclaimer">All pricing is indicative. Final pricing subject to site costs, council requirements, and builder contracts.</div>
        </div>
      </div>
    </div>
    <div class="continue-footer">
      <div class="continue-footer-left" id="customize-footer-info"></div>
      <button class="continue-btn" onclick="continueFromCustomize()">
        Review &amp; Submit EOI <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════ -->
  <!-- VIEW: SUMMARY & EOI                            -->
  <!-- ══════════════════════════════════════════════ -->
  <div class="view" id="view-summary" style="flex-direction:column">
    <div class="summary-hero">
      <div class="summary-hero-left">
        <div class="lbl">Total Indicative Package Price</div>
        <div class="amount" id="summary-total">—</div>
        <div class="qualifier">Land + Build + Customisations (indicative)</div>
      </div>
      <div class="summary-hero-right">
        <div class="proj-name" id="summary-project-name"></div>
        <div class="proj-sub" id="summary-project-sub"></div>
      </div>
    </div>
    <div class="summary-grid">
      <div class="summary-card">
        <h4>Lot Details</h4>
        <div id="summary-lot"></div>
      </div>
      <div class="summary-card">
        <h4>Home Design</h4>
        <div id="summary-design"></div>
      </div>
      <div class="summary-card">
        <h4>Customisations</h4>
        <div id="summary-custom"></div>
      </div>
      <div class="summary-card">
        <h4>Indicative Pricing</h4>
        <div id="summary-pricing"></div>
      </div>
    </div>
    <div class="eoi-section">
      <div class="eoi-form-inner" id="eoi-form-inner">
        <h3>Expression of Interest</h3>
        <p class="eoi-sub">Complete the form and your ProjX consultant will be in touch within 1 business day.</p>
        <div class="form-grid">
          <div class="form-field"><label>First Name *</label><input type="text" id="eoi-fname" placeholder="First name"/></div>
          <div class="form-field"><label>Last Name *</label><input type="text" id="eoi-lname" placeholder="Last name"/></div>
          <div class="form-field"><label>Email Address *</label><input type="email" id="eoi-email" placeholder="your@email.com"/></div>
          <div class="form-field"><label>Phone Number *</label><input type="tel" id="eoi-phone" placeholder="0400 000 000"/></div>
          <div class="form-field"><label>Preferred Contact Time</label>
            <select id="eoi-time">
              <option>Anytime</option><option>Morning (8am–12pm)</option>
              <option>Afternoon (12pm–5pm)</option><option>Evening (5pm–7pm)</option>
            </select>
          </div>
          <div class="form-field"><label>How did you hear about us?</label>
            <select id="eoi-source">
              <option>Via ProjX Consultant</option><option>Website</option>
              <option>Social Media</option><option>Referral</option><option>Other</option>
            </select>
          </div>
          <div class="form-field full"><label>Additional Notes</label><textarea id="eoi-notes" placeholder="Questions or additional requirements?"></textarea></div>
        </div>
        <div class="eoi-disclaimer">By submitting this Expression of Interest, you acknowledge all pricing shown is indicative only and subject to change. This EOI does not constitute a binding contract. A ProjX consultant will contact you to discuss formal contracts and final pricing.</div>
        <div class="validation-msg" id="err-eoi">Please fill in all required fields.</div>
        <button class="btn-submit" onclick="submitEOI()">Submit Expression of Interest →</button>
      </div>
      <div class="success-state" id="eoi-success">
        <div class="success-icon">✅</div>
        <h3>EOI Submitted!</h3>
        <p>Your ProjX consultant will be in touch within 1 business day to progress your Expression of Interest.</p>
        <p style="margin-top:16px;font-size:12px;color:var(--text-xlight)">Reference: <strong id="eoi-ref"></strong></p>
      </div>
    </div>
  </div>

</div><!-- /app -->

<script>
// ── Injected Data ─────────────────────────────────────────────────────────────
const ALL_LOTS = __ALL_LOTS_DATA__;
const PROJECTS = __PROJECTS_DATA__;
const BUILD_DATE = "__BUILD_DATE__";

const BUILDERS = [
  {id:'nexgen', name:'NexGen Homes', initials:'NG', tagline:'Smart homes, smarter value',
   tier:'Entry', tierKey:'entry', priceRange:'$250k–$350k', buildTime:'7–9 months',
   style:'Contemporary & functional', color:'#059669', emoji:'🏠'},
  {id:'avia', name:'AVIA Homes', initials:'AV', tagline:'Design-led homes, built to last',
   tier:'Entry–Mid', tierKey:'entry-mid', priceRange:'$280k–$380k', buildTime:'8–10 months',
   style:'Modern & design-led', color:'#1D4ED8', emoji:'🏡'},
  {id:'homecorp', name:'Homecorp', initials:'HC', tagline:'More space, more life',
   tier:'Mid', tierKey:'mid', priceRange:'$350k–$450k', buildTime:'9–12 months',
   style:'Spacious family homes', color:'#6D28D9', emoji:'🏘️'},
  {id:'coral', name:'Coral Homes', initials:'CL', tagline:'Crafted for Queensland living',
   tier:'Mid–Premium', tierKey:'mid-premium', priceRange:'$400k–$550k', buildTime:'10–14 months',
   style:'Premium QLD lifestyle', color:'#9D174D', emoji:'🌺'},
  {id:'bold', name:'Bold Living', initials:'BL', tagline:'Where architecture meets lifestyle',
   tier:'Premium', tierKey:'premium', priceRange:'$500k+', buildTime:'12–16 months',
   style:'Architectural premium homes', color:'#B45309', emoji:'✨'}
];

const DESIGNS = [
  {id:'ng1',builder:'nexgen',name:'Vibe 18',bed:3,bath:2,car:1,study:0,sqm:168,minFrontage:10,basePrice:258000,highlight:'Compact & clever'},
  {id:'ng2',builder:'nexgen',name:'Edge 20',bed:4,bath:2,car:2,study:0,sqm:188,minFrontage:12,basePrice:278000,highlight:'Best-selling design'},
  {id:'ng3',builder:'nexgen',name:'Flow 24',bed:4,bath:2,car:2,study:0,sqm:210,minFrontage:12,basePrice:299000,highlight:'Open-plan living'},
  {id:'av1',builder:'avia',name:'Gemini 220',bed:4,bath:2,car:2,study:0,sqm:220,minFrontage:12,basePrice:315000,highlight:'Family favourite'},
  {id:'av2',builder:'avia',name:'Prism 240',bed:4,bath:2,car:2,study:1,sqm:240,minFrontage:14,basePrice:348000,highlight:'With home office'},
  {id:'av3',builder:'avia',name:'Apex 260',bed:4,bath:2,car:2,study:0,sqm:258,minFrontage:14,basePrice:365000,highlight:"Entertainer's layout"},
  {id:'hc1',builder:'homecorp',name:'Sherwood 28',bed:4,bath:2,car:2,study:0,sqm:275,minFrontage:14,basePrice:378000,highlight:'Generous living'},
  {id:'hc2',builder:'homecorp',name:'Ridgeline 32',bed:4,bath:3,car:2,study:0,sqm:318,minFrontage:16,basePrice:425000,highlight:'3 bathrooms'},
  {id:'hc3',builder:'homecorp',name:'Bridgewater 35',bed:5,bath:3,car:2,study:0,sqm:348,minFrontage:16,basePrice:445000,highlight:'5-bedroom family'},
  {id:'cl1',builder:'coral',name:'Essence 310',bed:4,bath:2,car:2,study:1,sqm:312,minFrontage:16,basePrice:455000,highlight:'Alfresco focused'},
  {id:'cl2',builder:'coral',name:'Crest 340',bed:4,bath:3,car:3,study:0,sqm:338,minFrontage:18,basePrice:495000,highlight:'Triple garage'},
  {id:'cl3',builder:'coral',name:'Horizon 370',bed:5,bath:3,car:3,study:1,sqm:372,minFrontage:18,basePrice:525000,highlight:'Ultimate family home'},
  {id:'bl1',builder:'bold',name:'Magnolia 390',bed:4,bath:3,car:2,study:1,sqm:392,minFrontage:18,basePrice:545000,highlight:'Architectural icon'},
  {id:'bl2',builder:'bold',name:'Sovereign 420',bed:5,bath:3,car:3,study:1,sqm:418,minFrontage:20,basePrice:565000,highlight:'Statement living'},
  {id:'bl3',builder:'bold',name:'Prestige 450',bed:5,bath:4,car:3,study:0,sqm:452,minFrontage:20,basePrice:620000,highlight:'Pinnacle of luxury'}
];

const FACADES = [
  {id:'standard', name:'Standard', desc:'Classic rendered facade', premium:0, color:'#64748B'},
  {id:'modern', name:'Modern', desc:'Clean lines, feature cladding', premium:8500, color:'#1E40AF'},
  {id:'hamptons', name:'Hamptons', desc:'Coastal elegance, weatherboard detail', premium:12000, color:'#0F766E'},
  {id:'contemporary', name:'Contemporary', desc:'Bold angles, mixed materials', premium:7500, color:'#7C3AED'}
];

const INCLUSIONS = [
  {id:'standard', name:'Standard', desc:'Stone-look benchtops, stainless appliances, LED lighting.', premium:0},
  {id:'premium', name:'Premium', desc:'20mm stone benchtops, premium appliances, upgraded carpet & tiles, feature walls.', premium:28000},
  {id:'luxury', name:'Luxury', desc:'40mm stone, Bosch/Smeg appliances, engineered timber floors, custom cabinetry, smart home pre-wire.', premium:62000}
];

const UPGRADES = [
  {id:'ac', icon:'❄️', name:'Ducted Air Conditioning', desc:'7-zone ducted reverse-cycle system', price:12500},
  {id:'stone', icon:'🪨', name:'Stone Benchtops', desc:'20mm engineered stone throughout', price:4500},
  {id:'ceilings', icon:'📐', name:'2700mm Ceilings', desc:'Elevated ceiling heights throughout', price:3800},
  {id:'flooring', icon:'🪵', name:'Upgraded Flooring', desc:'Luxury vinyl plank in living areas', price:6200},
  {id:'solar', icon:'☀️', name:'Solar System (6.6kW)', desc:'6.6kW solar + monitoring system', price:7900},
  {id:'theatre', icon:'🎬', name:'Theatre Room Setup', desc:'Acoustic walls, recessed lighting, pre-wire', price:8500},
  {id:'butler', icon:'🍽️', name:"Butler's Pantry", desc:"Full butler's pantry with sink & storage", price:11000},
  {id:'alfresco', icon:'🌿', name:'Alfresco Extension', desc:'Extended covered outdoor entertaining area', price:18500}
];

// ── App State ─────────────────────────────────────────────────────────────────
const S = {
  path: null,              // 'land' | 'builder'
  project: null,           // selected project object
  lot: null,               // selected lot object
  selectedBuilders: [],    // array of builder ids (land-first)
  selectedBuilderObj: null,// builder object (builder-first)
  selectedDesign: null,    // design object
  facade: 'standard',
  inclusions: 'standard',
  upgrades: [],
  designFilter: 'all',
  currentView: 'landing'
};

let leafletMap = null;
const mapMarkers = {};

// ── Auth ──────────────────────────────────────────────────────────────────────
function checkAccess() {
  const inp = document.getElementById('gate-pass');
  if (inp.value === 'LV9') {
    document.getElementById('auth-gate').classList.add('hidden');
    document.getElementById('app').classList.add('visible');
    sessionStorage.setItem('portal-auth','1');
    initApp();
  } else {
    inp.classList.add('error'); inp.value = '';
    setTimeout(()=>inp.classList.remove('error'), 500);
  }
}
document.getElementById('gate-pass').addEventListener('keydown', e=>{ if(e.key==='Enter') checkAccess(); });
if (sessionStorage.getItem('portal-auth')==='1') {
  document.getElementById('auth-gate').classList.add('hidden');
  document.getElementById('app').classList.add('visible');
  initApp();
}

// ── Init ──────────────────────────────────────────────────────────────────────
function initApp() {
  renderBuilderShowcase();
  initMap();
}

// ── Formatters ────────────────────────────────────────────────────────────────
function fmt(n) { return '$' + Math.round(n).toLocaleString('en-AU'); }

// ── View Router ───────────────────────────────────────────────────────────────
function showView(viewId) {
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  const el = document.getElementById('view-' + viewId);
  if (el) el.classList.add('active');
  S.currentView = viewId;
  document.getElementById('top-home-btn').classList.toggle('visible', viewId !== 'landing');
  updateBreadcrumb();
  window.scrollTo({top:0, behavior:'smooth'});
}

function goHome() {
  S.path = null; S.project = null; S.lot = null;
  S.selectedBuilders = []; S.selectedBuilderObj = null; S.selectedDesign = null;
  S.facade = 'standard'; S.inclusions = 'standard'; S.upgrades = [];
  showView('landing');
  if (leafletMap) setTimeout(()=>leafletMap.invalidateSize(), 300);
}

function startLandFirst() {
  S.path = 'land';
  // Scroll map into view / hint user to click a pin
  window.scrollTo({top:0, behavior:'smooth'});
  if (leafletMap) leafletMap.invalidateSize();
}

function startBuilderFirst() {
  S.path = 'builder';
  document.getElementById('builder-showcase').scrollIntoView({behavior:'smooth'});
}

function scrollToBuilders() {
  S.path = 'builder';
  document.getElementById('builder-showcase').scrollIntoView({behavior:'smooth'});
}

function scrollToEntryPaths() {
  document.getElementById('entry-paths').scrollIntoView({behavior:'smooth'});
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────
function updateBreadcrumb() {
  const bc = document.getElementById('breadcrumb');
  const items = [];
  const homeItem = `<span class="bc-item clickable" onclick="goHome()">🗺 Map</span>`;

  if (S.currentView === 'landing') {
    bc.innerHTML = `<span class="bc-item current">🗺 Map &amp; Overview</span>`;
    return;
  }

  const sep = `<span class="bc-sep">›</span>`;

  if (S.path === 'land') {
    items.push(homeItem);
    if (S.project) items.push(`<span class="bc-item${S.currentView==='lots'?' current':' clickable'}" onclick="${S.currentView!=='lots'?"showView('lots')":""}"> ${S.project.name}</span>`);
    if (S.lot) items.push(`<span class="bc-item${S.currentView==='lot-builders'?' current':' clickable'}" onclick="${S.currentView!=='lot-builders'?"showView('lot-builders')":""}"> ${S.lot.name}</span>`);
    if (S.currentView==='lot-designs') items.push(`<span class="bc-item current">Designs</span>`);
    if (S.currentView==='customize') items.push(`<span class="bc-item current">Customise</span>`);
    if (S.currentView==='summary') items.push(`<span class="bc-item current">Review &amp; EOI</span>`);
  } else if (S.path === 'builder') {
    items.push(homeItem);
    if (S.selectedBuilderObj) items.push(`<span class="bc-item${S.currentView==='builder-browse'?' current':' clickable'}" onclick="${S.currentView!=='builder-browse'?"showView('builder-browse')":""}">${S.selectedBuilderObj.name}</span>`);
    if (S.selectedDesign && S.currentView !== 'builder-browse') items.push(`<span class="bc-item${S.currentView==='design-lots'?' current':' clickable'}" onclick="${S.currentView!=='design-lots'?"showView('design-lots')":""}">${S.selectedDesign.name}</span>`);
    if (S.currentView==='customize') items.push(`<span class="bc-item current">Customise</span>`);
    if (S.currentView==='summary') items.push(`<span class="bc-item current">Review &amp; EOI</span>`);
  }

  bc.innerHTML = items.join(sep);
}

// ── Map ───────────────────────────────────────────────────────────────────────
function initMap() {
  leafletMap = L.map('map', {zoomControl:true, scrollWheelZoom:true});

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains:'abcd', maxZoom:20
  }).addTo(leafletMap);

  const pinBounds = [];

  PROJECTS.forEach(proj => {
    const lots = ALL_LOTS[proj.id] || [];
    const avail = lots.filter(l=>l.availability==='Available').length;
    const prices = lots.filter(l=>l.price>0).map(l=>l.price);
    const minP = prices.length ? Math.min(...prices) : 0;
    const maxP = prices.length ? Math.max(...prices) : 0;

    const icon = L.divIcon({
      className:'',
      html:`<div class="map-pin-wrap">
        <div class="map-pin-circle"><span class="map-pin-count">${avail||lots.length}</span></div>
        <div class="map-pin-label-tag">${proj.name}</div>
      </div>`,
      iconSize:[80,64], iconAnchor:[40,44], popupAnchor:[0,-48]
    });

    const priceStr = minP && maxP ? fmt(minP) + ' – ' + fmt(maxP) : minP ? 'From ' + fmt(minP) : 'POA';

    const popupHtml = `<div class="popup-inner">
      <div class="popup-project-name">${proj.name}</div>
      <div class="popup-suburb">${proj.suburb}, ${proj.region} ${proj.emoji}</div>
      <div class="popup-stats">
        <div class="popup-stat"><div class="popup-stat-val">${avail||lots.length}</div><div class="popup-stat-lbl">Avail Lots</div></div>
        <div class="popup-stat"><div class="popup-stat-val">${lots.length}</div><div class="popup-stat-lbl">Total Lots</div></div>
      </div>
      <div class="popup-price">Land from <strong>${priceStr}</strong></div>
      <button class="popup-btn" onclick="viewProjectLots('${proj.id}')">View Lots →</button>
    </div>`;

    const marker = L.marker([proj.lat, proj.lng], {icon}).addTo(leafletMap);
    marker.bindPopup(popupHtml, {maxWidth:260, minWidth:240});
    mapMarkers[proj.id] = marker;
    pinBounds.push([proj.lat, proj.lng]);
  });

  if (pinBounds.length) {
    leafletMap.setView([-25.5, 152.5], 6);
  }
}

// ── Map Filter Logic ──────────────────────────────────────────────────────────
const BUILDER_MID_PRICES = {};
BUILDERS.forEach(b => {
  const m = b.priceRange.match(/\$(\d+)k/g);
  if (m && m.length >= 2) {
    const lo = parseInt(m[0].replace(/[$k]/g,'')) * 1000;
    const hi = parseInt(m[1].replace(/[$k]/g,'')) * 1000;
    BUILDER_MID_PRICES[b.id] = (lo + hi) / 2;
  } else if (m && m.length === 1) {
    BUILDER_MID_PRICES[b.id] = parseInt(m[0].replace(/[$k]/g,'')) * 1000 + 50000;
  }
});

const REGION_MAP = __REGION_MAP_DATA__;
const REGION_BOUNDS = __REGION_BOUNDS_DATA__;

const mapFilterState = {price:'any',beds:'any',region:'all',timeline:'all'};

function setMapChip(btn){
  const group = btn.getAttribute('data-filter');
  const val = btn.getAttribute('data-val');
  document.querySelectorAll('[data-filter="'+group+'"]').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  if(group==='mf-beds') mapFilterState.beds=val;
  else if(group==='mf-region') mapFilterState.region=val;
  else if(group==='mf-timeline') mapFilterState.timeline=val;
  applyMapFilters();
}

function applyMapFilters(){
  mapFilterState.price = document.getElementById('mf-price').value;
  const isFiltered = mapFilterState.price!=='any'||mapFilterState.beds!=='any'||mapFilterState.region!=='all'||mapFilterState.timeline!=='all';
  document.getElementById('mfb-clear').style.display = isFiltered?'block':'none';
  document.getElementById('mf-price').classList.toggle('has-val',mapFilterState.price!=='any');

  if(mapFilterState.region!=='all'&&REGION_BOUNDS[mapFilterState.region]){
    leafletMap.fitBounds(REGION_BOUNDS[mapFilterState.region],{padding:[60,60],maxZoom:11});
  } else if(mapFilterState.region==='all'){
    leafletMap.setView([-25.5, 152.5], 6);
  }

  const builderMids = Object.values(BUILDER_MID_PRICES);

  PROJECTS.forEach(proj=>{
    const lots = ALL_LOTS[proj.id]||[];
    const marker = mapMarkers[proj.id];
    if(!marker) return;
    let passes = true;

    // Price filter: lot_price + any builder midpoint in range
    if(mapFilterState.price!=='any'){
      let hasMatch=false;
      lots.forEach(l=>{
        if(l.price<=0) return;
        builderMids.forEach(mid=>{
          if(priceInRange(l.price+mid,mapFilterState.price)) hasMatch=true;
        });
      });
      if(!hasMatch) passes=false;
    }

    // Bedrooms: check if any design with that bed count fits any lot in this project
    if(mapFilterState.beds!=='any'){
      const target=parseInt(mapFilterState.beds);
      const isPlus=mapFilterState.beds==='5';
      const matchDesigns=DESIGNS.filter(d=>isPlus?d.bed>=target:d.bed===target);
      if(!matchDesigns.length){passes=false;}
      else{
        const hasCompat=lots.some(l=>matchDesigns.some(d=>l.frontage>=d.minFrontage));
        if(!hasCompat) passes=false;
      }
    }

    // Region
    if(mapFilterState.region!=='all'){
      const rp=REGION_MAP[mapFilterState.region]||[];
      if(!rp.includes(proj.id)) passes=false;
    }

    // Timeline
    if(mapFilterState.timeline!=='all'){
      const hasAvail=lots.some(l=>l.availability==='Available');
      const allUnreleased=lots.length>0&&lots.every(l=>l.availability==='Unreleased');
      if(mapFilterState.timeline==='ready'&&!hasAvail) passes=false;
      if(mapFilterState.timeline==='coming'&&!allUnreleased) passes=false;
    }

    updateMarkerStyle(proj,marker,passes);
  });
}

function priceInRange(pkg,range){
  switch(range){
    case '0-450':return pkg<450000;
    case '450-550':return pkg>=450000&&pkg<=550000;
    case '550-650':return pkg>=550000&&pkg<=650000;
    case '650-750':return pkg>=650000&&pkg<=750000;
    case '750-up':return pkg>=750000;
    default:return true;
  }
}

function updateMarkerStyle(proj,marker,active){
  const lots=ALL_LOTS[proj.id]||[];
  const avail=lots.filter(l=>l.availability==='Available').length;
  const f=active?'':' faded';
  const icon=L.divIcon({
    className:'',
    html:'<div class="map-pin-wrap"><div class="map-pin-circle'+f+'"><span class="map-pin-count">'+(avail||lots.length)+'</span></div><div class="map-pin-label-tag'+f+'">'+proj.name+'</div></div>',
    iconSize:[80,64],iconAnchor:[40,44],popupAnchor:[0,-48]
  });
  marker.setIcon(icon);
}

function clearMapFilters(){
  mapFilterState.price='any';mapFilterState.beds='any';mapFilterState.region='all';mapFilterState.timeline='all';
  document.getElementById('mf-price').value='any';
  document.querySelectorAll('.mfb-chip').forEach(c=>{
    const v=c.getAttribute('data-val');
    c.classList.toggle('active',v==='any'||v==='all');
  });
  applyMapFilters();
}

function viewProjectLots(projectId) {
  S.path = 'land';
  S.project = PROJECTS.find(p=>p.id===projectId);
  S.lot = null;
  S.selectedBuilders = [];
  S.selectedDesign = null;
  const lots = ALL_LOTS[projectId] || [];
  const avail = lots.filter(l=>l.availability==='Available').length;
  const prices = lots.filter(l=>l.price>0).map(l=>l.price);
  document.getElementById('lots-header-title').textContent = S.project.name + ' — Available Lots';
  document.getElementById('lots-header-sub').textContent = S.project.suburb + ', ' + S.project.region + ' · ' + avail + ' lots available';
  renderLots();
  showView('lots');
  if (leafletMap) { try { leafletMap.closePopup(); } catch(e){} }
}

// ── Builder Showcase ──────────────────────────────────────────────────────────
function renderBuilderShowcase() {
  const scroll = document.getElementById('builder-showcase-scroll');
  scroll.innerHTML = BUILDERS.map(b => `
    <div class="bs-card" onclick="viewBuilderDesigns('${b.id}')">
      <div class="bs-card-logo" style="background:${b.color}">${b.initials}</div>
      <div class="bs-card-name">${b.name}</div>
      <div class="bs-card-tier ${b.tierKey}">${b.tier}</div>
      <div class="bs-card-detail"><span>${b.priceRange}</span></div>
      <div class="bs-card-detail"><span>⏱ ${b.buildTime}</span></div>
      <div class="bs-card-detail"><span style="color:rgba(203,210,216,0.5)">${b.style}</span></div>
      <div class="bs-card-cta">Browse Designs →</div>
    </div>`).join('');
}

// ── LOTS ──────────────────────────────────────────────────────────────────────
function renderLots(gridId, projectId) {
  const gId = gridId || 'lot-grid';
  const pId = projectId || (S.project ? S.project.id : null);
  const grid = document.getElementById(gId);
  if (!pId) { grid.innerHTML = '<div class="no-results"><div class="icon">🗺</div><p>Select a project first.</p></div>'; return; }

  let lots = (ALL_LOTS[pId] || []).slice();
  const sort = (document.getElementById('lot-sort')||{value:'price-asc'}).value;
  const status = (document.getElementById('lot-status')||{value:'all'}).value;
  const maxPrice = parseInt((document.getElementById('lot-max-price')||{value:'0'}).value)||0;

  if (status !== 'all') lots = lots.filter(l=>l.availability===status);
  if (maxPrice > 0) lots = lots.filter(l=>l.price<=maxPrice);

  if (sort==='price-asc') lots.sort((a,b)=>a.price-b.price);
  else if (sort==='price-desc') lots.sort((a,b)=>b.price-a.price);
  else if (sort==='size-asc') lots.sort((a,b)=>a.lot_size-b.lot_size);
  else if (sort==='size-desc') lots.sort((a,b)=>b.lot_size-a.lot_size);

  const lbl = document.getElementById('lot-count-label');
  if (lbl) lbl.textContent = lots.length + ' lot' + (lots.length!==1?'s':'') + ' shown';

  if (!lots.length) {
    grid.innerHTML = '<div class="no-results"><div class="icon">🔍</div><p>No lots match your filters.</p></div>';
    return;
  }

  grid.innerHTML = lots.map(l => {
    const isSelected = S.lot && S.lot.id === l.id;
    const proj = PROJECTS.find(p=>p.id===l.project);
    const showProject = gId === 'design-lots-grid';
    return `
    <div class="lot-card ${isSelected?'selected':''}" onclick="selectLot('${l.id}','${gId}')">
      <div class="lot-card-head">
        <div>
          <div class="lot-name">${l.name}${showProject && proj ? ' <span style="font-size:11px;color:var(--text-xlight)">· '+proj.name+'</span>':''}</div>
          <div class="lot-stage">${l.stage||'Stage 1'} · ${l.type||'H&L'}</div>
        </div>
        <div class="lot-avail ${l.availability}">${l.availability}</div>
      </div>
      <div class="lot-specs">
        <div class="lot-spec"><div class="sv">${l.lot_size?l.lot_size.toLocaleString():'—'}</div><div class="sl">sqm</div></div>
        <div class="lot-spec"><div class="sv">${l.frontage}m</div><div class="sl">frontage</div></div>
      </div>
      <div class="lot-price-row">
        <div class="lot-price">${l.price?fmt(l.price):'POA'}</div>
        <button class="lot-select-btn">${isSelected?'✓ Selected':'Select'}</button>
      </div>
    </div>`;
  }).join('');
  updateLotsFooter();
}

function selectLot(id, gridId) {
  const pId = S.project ? S.project.id : null;
  let found = null;
  if (gridId === 'design-lots-grid') {
    for (const [pid, lots] of Object.entries(ALL_LOTS)) {
      found = lots.find(l=>l.id===id);
      if (found) { S.project = PROJECTS.find(p=>p.id===found.project)||S.project; break; }
    }
  } else {
    const lots = ALL_LOTS[pId] || [];
    found = lots.find(l=>l.id===id);
  }
  S.lot = found;
  document.getElementById('err-lots') && document.getElementById('err-lots').classList.remove('visible');
  document.getElementById('err-design-lots') && document.getElementById('err-design-lots').classList.remove('visible');
  renderLots(gridId, gridId==='design-lots-grid' ? null : pId);
  if (gridId === 'design-lots-grid') renderDesignLots();
  updateLotsFooter();
  updateDesignLotsFooter();
}

function updateLotsFooter() {
  const info = document.getElementById('lots-footer-info');
  if (info) info.innerHTML = S.lot ? `✓ <strong>${S.lot.name}</strong> — ${fmt(S.lot.price)} — ${S.lot.lot_size}m² · ${S.lot.frontage}m frontage` : 'Select a lot to continue';
}

function continueFromLots() {
  if (!S.lot) { document.getElementById('err-lots').classList.add('visible'); return; }
  renderBuilderSelectGrid();
  document.getElementById('lot-builders-sub').textContent = 'Lot ' + S.lot.name + ' has ' + S.lot.frontage + 'm frontage. Select up to 2 builders to explore compatible designs.';
  showView('lot-builders');
}

function renderBuilderSelectGrid() {
  const grid = document.getElementById('builder-select-grid');
  grid.innerHTML = BUILDERS.map(b => {
    const isSelected = S.selectedBuilders.includes(b.id);
    const isMaxed = !isSelected && S.selectedBuilders.length >= 2;
    return `
    <div class="builder-select-card ${isSelected?'selected':''} ${isMaxed?'maxed':''}" onclick="toggleBuilder('${b.id}')">
      <div class="bsc-check">${isSelected?'<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7l4 4 6-6" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>':''}</div>
      <div class="bsc-logo" style="background:${b.color}">${b.initials}</div>
      <div class="bsc-name">${b.name}</div>
      <div class="bsc-tagline">${b.tagline}</div>
      <div class="bsc-attrs">
        <div class="bsc-attr"><div class="bsc-attr-icon">💰</div><span class="bsc-attr-lbl">Build Price</span><span class="bsc-attr-val">${b.priceRange}</span></div>
        <div class="bsc-attr"><div class="bsc-attr-icon">🏗️</div><span class="bsc-attr-lbl">Build Time</span><span class="bsc-attr-val">${b.buildTime}</span></div>
        <div class="bsc-attr"><div class="bsc-attr-icon">🎨</div><span class="bsc-attr-lbl">Style</span><span class="bsc-attr-val" style="font-size:10px">${b.style}</span></div>
      </div>
      <div class="bsc-tier tier-${b.tierKey}">${b.tier}</div>
    </div>`;
  }).join('');
  updateBuildersFooter();
}

function toggleBuilder(id) {
  if (S.selectedBuilders.includes(id)) {
    S.selectedBuilders = S.selectedBuilders.filter(b=>b!==id);
  } else if (S.selectedBuilders.length < 2) {
    S.selectedBuilders.push(id);
  }
  document.getElementById('err-builders').classList.remove('visible');
  renderBuilderSelectGrid();
  updateBuildersFooter();
}

function updateBuildersFooter() {
  const info = document.getElementById('builders-footer-info');
  if (info) {
    const names = S.selectedBuilders.map(id=>{ const b=BUILDERS.find(b=>b.id===id); return b?b.name:''; });
    info.innerHTML = S.selectedBuilders.length > 0
      ? `✓ <strong>${names.join(' &amp; ')}</strong> selected`
      : '0/2 builders selected';
  }
}

function continueFromBuilders() {
  if (!S.selectedBuilders.length) { document.getElementById('err-builders').classList.add('visible'); return; }
  renderLotDesigns();
  showView('lot-designs');
}

function renderLotDesigns() {
  const frontage = S.lot ? S.lot.frontage : 99;
  const notice = document.getElementById('lot-designs-notice');
  if (S.lot && notice) {
    notice.style.display = 'block';
    notice.innerHTML = `<strong>Your Lot:</strong> ${S.lot.name} — ${S.lot.lot_size}m², ${frontage}m frontage. Designs requiring wider frontage are dimmed.`;
  }
  const designs = DESIGNS.filter(d=>S.selectedBuilders.includes(d.builder));
  renderDesignGrid(designs, 'lot-designs-grid', frontage, S.designFilter, 'lot-designs-count');
  updateLotDesignsFooter();
}

function filterDesigns(filter, btn, gridId) {
  S.designFilter = filter;
  const bar = btn.closest('.filter-bar');
  bar.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  if (gridId === 'lot-designs-grid') renderLotDesigns();
  else if (gridId === 'builder-designs-grid') renderBuilderDesigns();
}

function renderDesignGrid(designs, gridId, frontage, filter, countId) {
  let filtered = designs.slice();
  if (filter === 'compatible') filtered = filtered.filter(d=>d.minFrontage<=frontage);
  else if (filter === '4bed') filtered = filtered.filter(d=>d.bed>=4);
  else if (filter === '5bed') filtered = filtered.filter(d=>d.bed>=5);
  const countEl = document.getElementById(countId);
  if (countEl) countEl.textContent = filtered.length + ' design' + (filtered.length!==1?'s':'') + ' shown';
  const grid = document.getElementById(gridId);
  if (!filtered.length) {
    grid.innerHTML = '<div class="no-results"><div class="icon">🏠</div><p>No designs match the current filter.</p></div>';
    return;
  }
  grid.innerHTML = filtered.map(d => {
    const builder = BUILDERS.find(b=>b.id===d.builder);
    const compatible = d.minFrontage <= frontage;
    const isSelected = S.selectedDesign && S.selectedDesign.id === d.id;
    let badge = '';
    if (frontage < 99) {
      if (!compatible) badge = '<span class="design-compat-badge no">Needs '+d.minFrontage+'m+</span>';
      else if (d.minFrontage === frontage) badge = '<span class="design-compat-badge tight">Tight Fit</span>';
      else badge = '<span class="design-compat-badge fit">Fits Lot</span>';
    }
    const specs = [
      {icon:'🛏',val:d.bed+' Bed'},{icon:'🚿',val:d.bath+' Bath'},{icon:'🚗',val:d.car+' Car'},
      ...(d.study?[{icon:'📚',val:'Study'}]:[])
    ];
    return `
    <div class="design-card ${isSelected?'selected':''} ${frontage<99&&!compatible?'incompatible':''}" onclick="selectDesign('${d.id}','${gridId}')">
      <div class="design-thumb">
        <div class="design-thumb-bg" style="background:linear-gradient(135deg,${builder.color}18 0%,${builder.color}35 100%)"></div>
        <div class="design-thumb-icon">🏠</div>
        ${badge}
        <div class="design-thumb-overlay">
          <div class="design-thumb-name">${d.name}</div>
          <div class="design-thumb-builder">${builder.name} · ${d.highlight}</div>
        </div>
      </div>
      <div class="design-body">
        <div class="design-specs">${specs.map(s=>`<div class="design-spec-pill"><span>${s.icon}</span><span>${s.val}</span></div>`).join('')}</div>
        <div class="design-footer">
          <div>
            <div class="design-price">From ${fmt(d.basePrice)}</div>
            <div class="design-size">${d.sqm}m² internal</div>
            <div class="design-frontage-req">Min ${d.minFrontage}m frontage</div>
          </div>
        </div>
        <button class="design-select-btn">${isSelected?'✓ Selected':'Select Design'}</button>
      </div>
    </div>`;
  }).join('');
}

function selectDesign(id, gridId) {
  const d = DESIGNS.find(d=>d.id===id);
  S.selectedDesign = (S.selectedDesign && S.selectedDesign.id===id) ? null : d;
  document.getElementById('err-lot-designs') && document.getElementById('err-lot-designs').classList.remove('visible');
  document.getElementById('err-builder-designs') && document.getElementById('err-builder-designs').classList.remove('visible');
  if (gridId === 'lot-designs-grid') {
    const frontage = S.lot ? S.lot.frontage : 99;
    const designs = DESIGNS.filter(d=>S.selectedBuilders.includes(d.builder));
    renderDesignGrid(designs, 'lot-designs-grid', frontage, S.designFilter, 'lot-designs-count');
    updateLotDesignsFooter();
  } else if (gridId === 'builder-designs-grid') {
    const designs = S.selectedBuilderObj ? DESIGNS.filter(d=>d.builder===S.selectedBuilderObj.id) : [];
    renderDesignGrid(designs, 'builder-designs-grid', 99, S.designFilter, 'builder-designs-count');
    updateBuilderDesignsFooter();
  }
}

function updateLotDesignsFooter() {
  const info = document.getElementById('lot-designs-footer-info');
  if (info) info.innerHTML = S.selectedDesign ? `✓ <strong>${S.selectedDesign.name}</strong> selected` : 'Select a design to continue';
}

function continueFromLotDesigns() {
  if (!S.selectedDesign) { document.getElementById('err-lot-designs').classList.add('visible'); return; }
  renderCustomize();
  showView('customize');
}

function viewBuilderDesigns(builderId) {
  S.path = 'builder';
  S.selectedBuilderObj = BUILDERS.find(b=>b.id===builderId);
  S.selectedDesign = null;
  S.selectedBuilders = [builderId];
  S.designFilter = 'all';
  document.getElementById('builder-browse-title').textContent = S.selectedBuilderObj.name + ' — Home Designs';
  document.getElementById('builder-browse-sub').textContent = S.selectedBuilderObj.tagline + ' · ' + S.selectedBuilderObj.priceRange + ' · ' + S.selectedBuilderObj.buildTime;
  renderBuilderDesigns();
  showView('builder-browse');
}

function renderBuilderDesigns() {
  if (!S.selectedBuilderObj) return;
  const designs = DESIGNS.filter(d=>d.builder===S.selectedBuilderObj.id);
  renderDesignGrid(designs, 'builder-designs-grid', 99, S.designFilter, 'builder-designs-count');
  updateBuilderDesignsFooter();
}

function updateBuilderDesignsFooter() {
  const info = document.getElementById('builder-designs-footer-info');
  if (info) info.innerHTML = S.selectedDesign ? `✓ <strong>${S.selectedDesign.name}</strong> — find matching lots` : 'Select a design to find matching lots';
}

function continueFromBuilderDesigns() {
  if (!S.selectedDesign) { document.getElementById('err-builder-designs').classList.add('visible'); return; }
  populateDesignLotsFilters();
  renderDesignLots();
  document.getElementById('design-lots-sub').textContent = S.selectedDesign.name + ' requires min ' + S.selectedDesign.minFrontage + 'm frontage. These lots qualify.';
  showView('design-lots');
}

function populateDesignLotsFilters() {
  const sel = document.getElementById('design-lots-project-filter');
  sel.innerHTML = '<option value="all">All Projects</option>';
  PROJECTS.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id; opt.textContent = p.name;
    sel.appendChild(opt);
  });
}

function renderDesignLots() {
  if (!S.selectedDesign) return;
  const minFrontage = S.selectedDesign.minFrontage;
  const projFilter = (document.getElementById('design-lots-project-filter')||{value:'all'}).value;
  const statusFilter = (document.getElementById('design-lots-status')||{value:'all'}).value;
  let lots = [];
  Object.entries(ALL_LOTS).forEach(([pid, pLots]) => {
    if (projFilter !== 'all' && pid !== projFilter) return;
    pLots.forEach(l => { if (l.frontage >= minFrontage) lots.push(l); });
  });
  if (statusFilter !== 'all') lots = lots.filter(l=>l.availability===statusFilter);
  lots.sort((a,b)=>a.price-b.price);
  const countEl = document.getElementById('design-lots-count');
  if (countEl) countEl.textContent = lots.length + ' matching lot' + (lots.length!==1?'s':'');
  const grid = document.getElementById('design-lots-grid');
  if (!lots.length) {
    grid.innerHTML = '<div class="no-results"><div class="icon">🔍</div><p>No lots match. Try adjusting filters.</p></div>';
    return;
  }
  grid.innerHTML = lots.map(l => {
    const isSelected = S.lot && S.lot.id === l.id;
    const proj = PROJECTS.find(p=>p.id===l.project);
    return `
    <div class="lot-card ${isSelected?'selected':''}" onclick="selectLot('${l.id}','design-lots-grid')">
      <div class="lot-card-head">
        <div>
          <div class="lot-name">${l.name}</div>
          <div class="lot-stage">${proj?proj.name+' · ':''} ${l.stage||'Stage 1'}</div>
        </div>
        <div class="lot-avail ${l.availability}">${l.availability}</div>
      </div>
      <div class="lot-specs">
        <div class="lot-spec"><div class="sv">${l.lot_size?l.lot_size.toLocaleString():'—'}</div><div class="sl">sqm</div></div>
        <div class="lot-spec"><div class="sv">${l.frontage}m</div><div class="sl">frontage</div></div>
      </div>
      <div class="lot-price-row">
        <div class="lot-price">${l.price?fmt(l.price):'POA'}</div>
        <button class="lot-select-btn">${isSelected?'✓ Selected':'Select'}</button>
      </div>
    </div>`;
  }).join('');
}

function updateDesignLotsFooter() {
  const info = document.getElementById('design-lots-footer-info');
  if (info) info.innerHTML = S.lot ? `✓ <strong>${S.lot.name}</strong> — ${fmt(S.lot.price)}` : 'Select a lot to continue';
}

function continueFromDesignLots() {
  if (!S.lot) { document.getElementById('err-design-lots').classList.add('visible'); return; }
  renderCustomize();
  showView('customize');
}

function renderCustomize() {
  if (!S.selectedDesign) return;
  const d = S.selectedDesign;
  const b = BUILDERS.find(b=>b.id===d.builder);
  document.getElementById('pricing-preview').innerHTML =
    `<div class="pricing-design-name">${d.name}</div><div class="pricing-design-sub">${b.name} · ${d.bed}bd ${d.bath}ba ${d.car}car · ${d.sqm}m²</div>`;
  document.getElementById('facade-grid').innerHTML = FACADES.map(f=>`
    <div class="facade-option ${S.facade===f.id?'selected':''}" onclick="selectFacade('${f.id}')">
      <div class="facade-thumb"><div class="facade-thumb-bg" style="background:${f.color}22"></div><div class="facade-thumb-icon">🏠</div></div>
      <div class="facade-name">${f.name}</div>
      <div class="facade-price">${f.premium===0?'Included':'+'+fmt(f.premium)}</div>
    </div>`).join('');
  document.getElementById('inclusions-grid').innerHTML = INCLUSIONS.map(i=>`
    <div class="incl-option ${S.inclusions===i.id?'selected':''}" onclick="selectInclusions('${i.id}')">
      <div class="incl-name">${i.name}</div>
      <div class="incl-desc">${i.desc}</div>
      <div class="incl-price">${i.premium===0?'Included':'+'+fmt(i.premium)}</div>
    </div>`).join('');
  document.getElementById('upgrades-list').innerHTML = UPGRADES.map(u=>`
    <div class="upgrade-item ${S.upgrades.includes(u.id)?'selected':''}" onclick="toggleUpgrade('${u.id}')">
      <div class="upgrade-check">${S.upgrades.includes(u.id)?'<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>':''}</div>
      <div class="upgrade-icon">${u.icon}</div>
      <div class="upgrade-info"><div class="upgrade-name">${u.name}</div><div class="upgrade-desc">${u.desc}</div></div>
      <div class="upgrade-price">+${fmt(u.price)}</div>
    </div>`).join('');
  updatePricing();
}

function selectFacade(id) { S.facade=id; renderCustomize(); }
function selectInclusions(id) { S.inclusions=id; renderCustomize(); }
function toggleUpgrade(id) {
  S.upgrades = S.upgrades.includes(id) ? S.upgrades.filter(u=>u!==id) : [...S.upgrades, id];
  renderCustomize();
}

function updatePricing() {
  const d = S.selectedDesign; if (!d) return;
  const lot = S.lot;
  const facadeObj = FACADES.find(f=>f.id===S.facade);
  const inclObj = INCLUSIONS.find(i=>i.id===S.inclusions);
  const upgradeTotal = S.upgrades.reduce((sum,uid)=>{ const u=UPGRADES.find(u=>u.id===uid); return sum+(u?u.price:0); },0);
  const landPrice = lot ? lot.price : 0;
  const facadePremium = facadeObj ? facadeObj.premium : 0;
  const inclPremium = inclObj ? inclObj.premium : 0;
  const total = landPrice + d.basePrice + facadePremium + inclPremium + upgradeTotal;
  document.getElementById('price-land').textContent = lot ? fmt(landPrice) : 'TBC';
  document.getElementById('price-build').textContent = fmt(d.basePrice);
  document.getElementById('price-facade').textContent = facadePremium ? '+'+fmt(facadePremium) : 'Included';
  document.getElementById('price-inclusions').textContent = inclPremium ? '+'+fmt(inclPremium) : 'Standard';
  document.getElementById('price-upgrades').textContent = upgradeTotal ? '+'+fmt(upgradeTotal) : '$0';
  document.getElementById('price-total').textContent = fmt(total);
  const info = document.getElementById('customize-footer-info');
  if (info) info.innerHTML = `Total from <strong>${fmt(total)}</strong>`;
}

function getTotalPrice() {
  const d = S.selectedDesign; if (!d) return 0;
  const facadeObj = FACADES.find(f=>f.id===S.facade);
  const inclObj = INCLUSIONS.find(i=>i.id===S.inclusions);
  const upgradeTotal = S.upgrades.reduce((sum,uid)=>{ const u=UPGRADES.find(u=>u.id===uid); return sum+(u?u.price:0); },0);
  return (S.lot?S.lot.price:0)+d.basePrice+(facadeObj?facadeObj.premium:0)+(inclObj?inclObj.premium:0)+upgradeTotal;
}

function goBackFromCustomize() {
  if (S.path === 'land') showView('lot-designs');
  else showView('design-lots');
}

function continueFromCustomize() { renderSummary(); showView('summary'); }

function renderSummary() {
  const d = S.selectedDesign;
  const lot = S.lot;
  const proj = S.project || PROJECTS.find(p=>p.id===(lot?lot.project:null));
  const b = d ? BUILDERS.find(bl=>bl.id===d.builder) : null;
  const facadeObj = FACADES.find(f=>f.id===S.facade);
  const inclObj = INCLUSIONS.find(i=>i.id===S.inclusions);
  const upgradeTotal = S.upgrades.reduce((sum,uid)=>{ const u=UPGRADES.find(u=>u.id===uid); return sum+(u?u.price:0); },0);
  const total = getTotalPrice();
  document.getElementById('summary-total').textContent = fmt(total);
  document.getElementById('summary-project-name').textContent = proj ? proj.name : '';
  document.getElementById('summary-project-sub').textContent = proj ? proj.suburb + ', QLD' : '';
  document.getElementById('summary-lot').innerHTML = lot ? `
    <div class="summary-row"><span class="s-lbl">Lot</span><span class="s-val">${lot.name}</span></div>
    <div class="summary-row"><span class="s-lbl">Project</span><span class="s-val">${proj?proj.name:''}</span></div>
    <div class="summary-row"><span class="s-lbl">Land Size</span><span class="s-val">${lot.lot_size}m²</span></div>
    <div class="summary-row"><span class="s-lbl">Frontage</span><span class="s-val">${lot.frontage}m</span></div>
    <div class="summary-row"><span class="s-lbl">Land Price</span><span class="s-val">${fmt(lot.price)}</span></div>
    <div class="summary-row"><span class="s-lbl">Status</span><span class="s-val">${lot.availability}</span></div>` : '<p>No lot selected</p>';
  document.getElementById('summary-design').innerHTML = d ? `
    <div class="summary-row"><span class="s-lbl">Design</span><span class="s-val">${d.name}</span></div>
    <div class="summary-row"><span class="s-lbl">Builder</span><span class="s-val">${b?b.name:''}</span></div>
    <div class="summary-row"><span class="s-lbl">Bedrooms</span><span class="s-val">${d.bed} Bed / ${d.bath} Bath / ${d.car} Car${d.study?' + Study':''}</span></div>
    <div class="summary-row"><span class="s-lbl">Area</span><span class="s-val">${d.sqm}m²</span></div>
    <div class="summary-row"><span class="s-lbl">Base Price</span><span class="s-val">${fmt(d.basePrice)}</span></div>` : '<p>No design selected</p>';
  const upgradeRows = S.upgrades.map(uid=>{ const u=UPGRADES.find(u=>u.id===uid); return u?`<div class="summary-row"><span class="s-lbl">${u.name}</span><span class="s-val">+${fmt(u.price)}</span></div>`:''; }).join('');
  document.getElementById('summary-custom').innerHTML = `
    <div class="summary-row"><span class="s-lbl">Facade</span><span class="s-val">${facadeObj?facadeObj.name:''}</span></div>
    <div class="summary-row"><span class="s-lbl">Inclusions</span><span class="s-val">${inclObj?inclObj.name:''}</span></div>
    ${upgradeRows || '<div class="summary-row"><span class="s-lbl">Upgrades</span><span class="s-val">None</span></div>'}`;
  const facadePremium = facadeObj ? facadeObj.premium : 0;
  const inclPremium = inclObj ? inclObj.premium : 0;
  document.getElementById('summary-pricing').innerHTML = `
    <div class="summary-row"><span class="s-lbl">Land</span><span class="s-val">${lot?fmt(lot.price):'TBC'}</span></div>
    <div class="summary-row"><span class="s-lbl">Build Base</span><span class="s-val">${d?fmt(d.basePrice):'—'}</span></div>
    <div class="summary-row"><span class="s-lbl">Facade</span><span class="s-val">${facadePremium?'+'+fmt(facadePremium):'Included'}</span></div>
    <div class="summary-row"><span class="s-lbl">Inclusions</span><span class="s-val">${inclPremium?'+'+fmt(inclPremium):'Standard'}</span></div>
    <div class="summary-row"><span class="s-lbl">Upgrades</span><span class="s-val">${upgradeTotal?'+'+fmt(upgradeTotal):'$0'}</span></div>
    <div class="summary-row" style="font-weight:800"><span class="s-lbl" style="font-weight:700;color:var(--navy)">Total</span><span class="s-val" style="color:var(--accent)">${fmt(total)}</span></div>`;
}

function submitEOI() {
  const fname=document.getElementById('eoi-fname').value.trim();
  const lname=document.getElementById('eoi-lname').value.trim();
  const email=document.getElementById('eoi-email').value.trim();
  const phone=document.getElementById('eoi-phone').value.trim();
  if (!fname||!lname||!email||!phone) { document.getElementById('err-eoi').classList.add('visible'); return; }
  document.getElementById('err-eoi').classList.remove('visible');
  const ref='EOI-'+Date.now().toString(36).toUpperCase();
  document.getElementById('eoi-ref').textContent=ref;
  document.getElementById('eoi-form-inner').classList.add('hidden');
  document.getElementById('eoi-success').classList.add('visible');
}
</script>
</body>
</html>
"""


def build_projects_data(all_lots):
    """Build the PROJECTS JS array from PROJECTS_GEO and lot data."""
    projects = []
    emojis = {'Gold Coast': '🏙️', 'Brisbane South': '🏡', 'Brisbane North': '🏘️',
              'Brisbane': '🌆', 'Logan': '🏡', 'Moreton Bay': '🌳', 'Lockyer Valley': '🌾',
              'Scenic Rim': '🌿', 'Sunshine Coast': '☀️', 'Gympie': '🏞️',
              'Mackay': '🌴', 'Northern NSW': '🏖️'}
    for name, geo in PROJECTS_GEO.items():
        slug = make_slug(name)
        lots = all_lots.get(slug, [])
        avail = sum(1 for l in lots if l["availability"] == "Available")
        region = geo['region']
        projects.append({
            'id': slug,
            'name': name,
            'suburb': geo['suburb'],
            'region': region,
            'lat': geo['lat'],
            'lng': geo['lng'],
            'emoji': emojis.get(region, '📍'),
            'status': 'Selling Now' if avail > 0 else 'Coming Soon',
        })
    return projects


def build_region_map(projects_data):
    """Build REGION_MAP: {region_slug: [project_id, ...]}."""
    region_map = {}
    for p in projects_data:
        slug = p['region'].lower().replace(' ', '-')
        region_map.setdefault(slug, []).append(p['id'])
    return region_map


def build_region_bounds(projects_data):
    """Build REGION_BOUNDS from project coordinates."""
    region_coords = {}
    for p in projects_data:
        slug = p['region'].lower().replace(' ', '-')
        region_coords.setdefault(slug, []).append((p['lat'], p['lng']))
    bounds = {}
    for slug, coords in region_coords.items():
        lats = [c[0] for c in coords]
        lngs = [c[1] for c in coords]
        pad = 0.08
        bounds[slug] = [[min(lats) - pad, min(lngs) - pad], [max(lats) + pad, max(lngs) + pad]]
    return bounds


def build_region_chips(projects_data):
    """Build HTML region chip buttons from actual regions present."""
    seen = set()
    regions = []
    for r in REGION_ORDER:
        slug = r.lower().replace(' ', '-')
        if any(p['region'] == r for p in projects_data) and slug not in seen:
            regions.append((slug, r))
            seen.add(slug)
    # Add any regions not in REGION_ORDER
    for p in projects_data:
        slug = p['region'].lower().replace(' ', '-')
        if slug not in seen:
            regions.append((slug, p['region']))
            seen.add(slug)
    return '\n          '.join(
        f'<button class="mfb-chip" data-filter="mf-region" data-val="{slug}" onclick="setMapChip(this)">{name}</button>'
        for slug, name in regions
    )


def build_html(all_lots, projects_data, region_map, region_bounds, region_chips):
    now = datetime.datetime.now().strftime("%d %b %Y")
    html = HTML_TEMPLATE
    html = html.replace("__ALL_LOTS_DATA__", json.dumps(
        {p['id']: all_lots.get(p['id'], []) for p in projects_data}, ensure_ascii=False))
    html = html.replace("__PROJECTS_DATA__", json.dumps(projects_data, ensure_ascii=False))
    html = html.replace("__REGION_MAP_DATA__", json.dumps(region_map, ensure_ascii=False))
    html = html.replace("__REGION_BOUNDS_DATA__", json.dumps(region_bounds, ensure_ascii=False))
    html = html.replace("__REGION_CHIPS__", region_chips)
    html = html.replace("__BUILD_DATE__", now)
    return html


def main():
    print("🏗  ProjX House & Land Design Portal — V2.4 Build")
    print("=" * 55)
    try:
        token = get_token()
        print("✓  Monday.com token loaded")
    except Exception as e:
        print(f"✗  {e}")
        sys.exit(1)

    print("→  Fetching boards from workspace %d…" % WORKSPACE_ID, end="", flush=True)
    try:
        boards = fetch_workspace_boards(token)
        print(f" found {len(boards)} boards")
    except Exception as e:
        print(f"\n✗  Failed to fetch boards: {e}")
        sys.exit(1)

    # Match boards to PROJECTS_GEO by name
    all_lots = {}
    total_lots = 0
    total_avail = 0
    matched_boards = []

    for board in boards:
        board_name = board["name"]
        # Find matching geo entry (H&L allowlist only)
        geo_match = None
        for geo_name in PROJECTS_GEO:
            if geo_name.lower() == board_name.lower() or geo_name.lower() in board_name.lower() or board_name.lower() in geo_name.lower():
                geo_match = geo_name
                break
        if not geo_match:
            # Check if it's an excluded board vs truly unknown
            is_excluded = any(ex.lower() in board_name.lower() or board_name.lower() in ex.lower() for ex in EXCLUDED_BOARDS)
            if is_excluded:
                print(f"   ✗  Excluded (not H&L): {board_name}")
            else:
                print(f"   ⚠  Skipping unmatched board: {board_name}")
            continue
        if geo_match not in HL_ALLOWLIST:
            print(f"   ✗  Excluded (not H&L): {geo_match}")
            continue

        slug = make_slug(geo_match)
        print(f"   → {geo_match} (board {board['id']})…", end="", flush=True)
        try:
            lots = fetch_board_lots(board["id"], geo_match, token)
            avail = sum(1 for l in lots if l["availability"] == "Available")
            # Keep the board with the most lots (skip empty/template boards)
            if len(lots) > len(all_lots.get(slug, [])):
                old_count = len(all_lots.get(slug, []))
                if old_count > 0:
                    total_lots -= old_count
                    total_avail -= sum(1 for l in all_lots[slug] if l["availability"] == "Available")
                all_lots[slug] = lots
                total_lots += len(lots)
                total_avail += avail
                if geo_match not in matched_boards:
                    matched_boards.append(geo_match)
                print(f" {len(lots)} lots ({avail} avail)")
            else:
                print(f" {len(lots)} lots (skipped, keeping better board)")
        except Exception as e:
            print(f" FAILED: {e}")
            if slug not in all_lots:
                all_lots[slug] = []

    print(f"\n✓  Fetched {len(matched_boards)} projects, {total_lots} total lots, {total_avail} available")

    projects_data = build_projects_data(all_lots)
    region_map = build_region_map(projects_data)
    region_bounds = build_region_bounds(projects_data)
    region_chips = build_region_chips(projects_data)

    print("→  Generating HTML…", end="", flush=True)
    html = build_html(all_lots, projects_data, region_map, region_bounds, region_chips)
    print(" done")

    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"✓  Written: {out_path} ({size_kb:.0f} KB)")
    print()
    print("📦 Summary")
    for p in projects_data:
        lots = all_lots.get(p['id'], [])
        avail = sum(1 for l in lots if l["availability"] == "Available")
        tag = "live" if lots else "no data"
        print(f"   {p['name']:30s} {len(lots):3d} lots ({avail} avail) [{tag}]")
    print(f"   {'':30s} ─────────────")
    print(f"   {'TOTAL':30s} {total_lots:3d} lots ({total_avail} avail)")
    print(f"   Builders:      5")
    print(f"   Designs:       15")
    print(f"   Regions:       {len(set(p['region'] for p in projects_data))}")


if __name__ == "__main__":
    main()