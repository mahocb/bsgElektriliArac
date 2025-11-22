# server.py
import asyncio
import json
import time
import os
from typing import Dict, Any, Optional, List, Deque
from collections import deque

import websockets
from websockets.server import serve

from rules import RuleEngine, Anomaly  # mevcut kural setin

# ====== Yapılandırma ======
HOST, PORT = "localhost", 8765

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "events.jsonl")

# ====== AI (IsolationForest bundle) ======
import numpy as np
import pickle

AI_MODEL_PATH = os.path.join(LOG_DIR, "ai_model.joblib")
ai_bundle = None
if os.path.exists(AI_MODEL_PATH):
    try:
        with open(AI_MODEL_PATH, "rb") as f:
            ai_bundle = pickle.load(f)  # {"scaler","model","threshold","features"}
        print("[AI] model bundle loaded")
    except Exception as e:
        print(f"[AI] load error: {e}")
        ai_bundle = None
else:
    print("[AI] model bundle not found; running rule-based only")

def ai_predict(enriched_payload: Dict[str, Any]) -> bool:
    """
    IsolationForest kararını verir.
    enriched_payload: gerçek zamanda hesaplanmış türev/pencere alanlarını da içerir.
    True => anomali
    """
    if ai_bundle is None:
        return False
    try:
        feat = ai_bundle["features"]
        scaler = ai_bundle["scaler"]
        model  = ai_bundle["model"]
        th     = ai_bundle["threshold"]

        def g(k, default=0.0):
            v = enriched_payload.get(k, default)
            try:
                return float(v)
            except Exception:
                return float(default)

        x = np.array([[g(k, 0.0) for k in feat]], dtype=float)
        xs = scaler.transform(x)
        score = model.decision_function(xs)[0]  # büyükse daha normal
        return score < th
    except Exception as e:
        # AI hatası durumunda sessizce AI'yi pas geç
        return False

# ====== Log yardımcıları ======
def log_event(event: Dict[str, Any]):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[log] write error: {e}")

# ====== Bağlantı ID ======
_conn_id = 0
def next_conn_id():
    global _conn_id
    _conn_id += 1
    return _conn_id

# ====== Oturum durumu ======
class SessionState:
    def __init__(self, conn_id: int):
        self.conn_id = conn_id
        self.started = False
        self.authed = False
        self.fw_ok = True
        self.terminated = False

        # Gerçek zamanlı özellikler için önceki değerler
        self.prev_ts_ms: Optional[int] = None
        self.prev_power: Optional[float] = None
        self.prev_energy: Optional[float] = None

        # Kısa hareketli ortalama için pencere
        self.pow_win: Deque[float] = deque(maxlen=3)

# ====== Ana handler ======
async def handle(ws):
    conn_id = next_conn_id()
    state = SessionState(conn_id)
    engine = RuleEngine()
    peer = ws.remote_address
    print(f"[+] Connection #{conn_id} from {peer}")
    log_event({"ts": time.time(), "conn_id": conn_id, "type": "CONNECT", "peer": str(peer)})

    try:
        async for msg in ws:
            recv_ts = time.time()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                print(f"[#] #{conn_id} invalid JSON")
                log_event({"ts": recv_ts, "conn_id": conn_id, "type": "ERROR", "error": "INVALID_JSON"})
                continue

            mtype = data.get("type")
            payload = data.get("payload", {}) or {}
            anomalies: List[Anomaly] = []

            # ---- AUTH ----
            if mtype == "AUTH":
                ok, issue = engine.check_auth(payload)
                state.authed = ok
                if not ok and issue:
                    anomalies.append(issue)

            # ---- FIRMWARE ----
            elif mtype == "FIRMWARE":
                ok, issue = engine.check_firmware(payload)
                state.fw_ok = ok
                if not ok and issue:
                    anomalies.append(issue)

            # ---- START ----
            elif mtype == "START":
                state.started = True
                print(f"[#] #{conn_id} session START")

            # ---- METRICS ----
            elif mtype == "METRICS":
                # 1) Türev/pencere özelliklerini HESAPLA
                ts_ms = payload.get("ts")            # istasyonun ms timestamp'ı (int)
                power = payload.get("power_kw")
                energy = payload.get("energy_kwh")

                # Güvenli sayısallaştırma
                try: ts_ms = int(ts_ms) if ts_ms is not None else None
                except: ts_ms = None
                try: power = float(power) if power is not None else None
                except: power = None
                try: energy = float(energy) if energy is not None else None
                except: energy = None

                # dt / d_power / d_energy
                dt = None
                d_power = None
                d_energy = None
                if state.prev_ts_ms is not None and ts_ms is not None:
                    dt = max(1, ts_ms - state.prev_ts_ms)  # ms, 0'ı engelle
                if state.prev_power is not None and power is not None:
                    d_power = power - state.prev_power
                if state.prev_energy is not None and energy is not None:
                    d_energy = energy - state.prev_energy

                # power_ma3 / power_z
                if power is not None:
                    state.pow_win.append(power)
                if len(state.pow_win) > 0:
                    power_ma3 = sum(state.pow_win) / len(state.pow_win)
                else:
                    power_ma3 = power if power is not None else 0.0

                if len(state.pow_win) > 1:
                    mu = power_ma3
                    var = sum((x - mu) ** 2 for x in state.pow_win) / len(state.pow_win)
                    pow_std = var ** 0.5
                else:
                    pow_std = 0.0
                power_z = 0.0 if pow_std == 0 else ((power or 0.0) - power_ma3) / pow_std

                # payload'ı zenginleştir (AI aynı özellikleri görsün)
                enriched = dict(payload)
                enriched.update({
                    "dt": dt if dt is not None else 0.0,
                    "d_power": d_power if d_power is not None else 0.0,
                    "d_energy": d_energy if d_energy is not None else 0.0,
                    "power_ma3": power_ma3,
                    "power_z": power_z,
                })

                # 2) Şifreleme vb. kural kontrolleri
                anomalies.extend(engine.check_encryption(payload))
                issue = engine.check_metrics(payload, state)  # mevcut kuralların metriks kontrolü
                if issue:
                    anomalies.append(issue)

                # 3) Kural bulmadıysa AI ile kontrol et (MEDIUM olarak işaretle)
                if not anomalies and ai_predict(enriched):
                    anomalies.append(Anomaly(
                        code="AI_DETECTED",
                        severity="MEDIUM",
                        message="AI modeli anomalik örüntü tespit etti"
                    ))

                # 4) LOG
                stop_required = any(a.severity == "HIGH" for a in anomalies)
                log_event({
                    "ts": recv_ts,
                    "conn_id": conn_id,
                    "type": mtype,
                    "payload": enriched,  # zenginleştirilmiş payload'ı da yaz
                    "anomalies": [{"code": a.code, "sev": a.severity, "msg": a.message} for a in anomalies],
                    "action": "STOP_CHARGE" if stop_required else "ACK"
                })

                # 5) Konsola yaz
                for a in anomalies:
                    print(f"[!] #{conn_id} {a.code}: {a.message} (sev: {a.severity})")

                # 6) STOP veya ACK
                if stop_required:
                    cmd = {"type": "CMD", "cmd": "STOP_CHARGE", "reason": anomalies[0].code}
                    await ws.send(json.dumps(cmd))
                    print(f"[>] #{conn_id} -> STOP_CHARGE sent; closing")
                    # ISTASYONA fırsat vermeden bağlantıyı kes (yarış yaralarını önler)
                    await ws.close()
                    break
                else:
                    await ws.send(json.dumps({"type": "ACK", "ok": True}))

                # 7) State'i güncelle
                if ts_ms is not None:
                    state.prev_ts_ms = ts_ms
                if power is not None:
                    state.prev_power = power
                if energy is not None:
                    state.prev_energy = energy

            # ---- STOP ----
            elif mtype == "STOP":
                print(f"[#] #{conn_id} session STOP by station")
                log_event({"ts": recv_ts, "conn_id": conn_id, "type": "STOP"})
                await ws.close()
                break

            else:
                print(f"[#] #{conn_id} unknown message: {mtype}")

    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"[-] Connection #{conn_id} closed")
        log_event({"ts": time.time(), "conn_id": conn_id, "type": "DISCONNECT"})

# ====== main ======
async def main():
    async with serve(handle, HOST, PORT):
        print(f"CSMS listening on ws://{HOST}:{PORT}")
        print(f"Logging to {LOG_FILE}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
