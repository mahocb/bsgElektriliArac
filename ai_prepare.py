# ai_prepare.py (v2) — JSONL -> CSV + zaman-türev özellikleri
import json, csv
from pathlib import Path
from collections import defaultdict
import math

src = Path("data/events.jsonl")
dst = Path("data/events.csv")

# conn_id bazında ardışık kayıtları tutalım ki dt, d_power hesaplayalım
buf = defaultdict(list)

with src.open() as f:
    for line in f:
        try:
            obj = json.loads(line)
        except:
            continue
        if obj.get("type") != "METRICS":
            continue
        p = obj.get("payload") or {}
        if not all(k in p for k in ("voltage","current","power_kw","energy_kwh","temp_c","ts","seq")):
            continue
        cid = obj.get("conn_id")
        buf[cid].append({
            "ts_server": obj.get("ts"),         # server ts (s)
            "ts_ms": p.get("ts"),               # payload ts (ms)
            "conn_id": cid,
            "voltage": p["voltage"],
            "current": p["current"],
            "power_kw": p["power_kw"],
            "energy_kwh": p["energy_kwh"],
            "temp_c": p["temp_c"],
            "enc": int(bool(p.get("enc"))),
            "seq": p["seq"],
            "codes": ",".join(a.get("code","") for a in (obj.get("anomalies") or []) if isinstance(a,dict)),
        })

# conn içinde sıralayıp türev/pencere üret
rows = []
for cid, lst in buf.items():
    lst.sort(key=lambda x: (x["ts_ms"], x["seq"]))
    prev = None
    ma_win = []  # moving window for power
    for rec in lst:
        dt = None
        d_power = None
        d_energy = None
        if prev and rec["ts_ms"] is not None and prev["ts_ms"] is not None:
            dt = max(1, rec["ts_ms"] - prev["ts_ms"])  # ms, 0 olmasın
            d_power = rec["power_kw"] - prev["power_kw"]
            d_energy = rec["energy_kwh"] - prev["energy_kwh"]
        # moving avg / std (3’lük)
        ma_win.append(rec["power_kw"])
        if len(ma_win) > 3:
            ma_win.pop(0)
        power_ma3 = sum(ma_win)/len(ma_win)
        # std
        if len(ma_win) > 1:
            mu = power_ma3
            var = sum((x-mu)**2 for x in ma_win)/len(ma_win)
            power_std3 = math.sqrt(var)
        else:
            power_std3 = 0.0
        power_z = 0.0 if power_std3 == 0 else (rec["power_kw"] - power_ma3)/power_std3

        rows.append({
            "ts_server": rec["ts_server"],
            "ts_ms": rec["ts_ms"],
            "conn_id": rec["conn_id"],
            "voltage": rec["voltage"],
            "current": rec["current"],
            "power_kw": rec["power_kw"],
            "energy_kwh": rec["energy_kwh"],
            "temp_c": rec["temp_c"],
            "enc": rec["enc"],
            "seq": rec["seq"],
            "dt": dt,
            "d_power": d_power,
            "d_energy": d_energy,
            "power_ma3": power_ma3,
            "power_z": power_z,
            "label": "ANOMALY" if rec["codes"] else "NORMAL",
            "codes": rec["codes"],
        })
        prev = rec

with dst.open("w", newline="") as w:
    wr = csv.writer(w)
    wr.writerow(["ts_server","ts_ms","conn_id","voltage","current","power_kw","energy_kwh","temp_c",
                 "enc","seq","dt","d_power","d_energy","power_ma3","power_z","label","codes"])
    for r in rows:
        wr.writerow([r["ts_server"], r["ts_ms"], r["conn_id"], r["voltage"], r["current"], r["power_kw"],
                     r["energy_kwh"], r["temp_c"], r["enc"], r["seq"], r["dt"], r["d_power"], r["d_energy"],
                     r["power_ma3"], r["power_z"], r["label"], r["codes"]])

print(f"[OK] wrote {dst} with {len(rows)} rows")
