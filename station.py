import asyncio
import json
import random
import time
import argparse
import websockets

HOST, PORT = "localhost", 8765

def now_ms():
    return int(time.time()*1000)

async def simulate(scenario: str):
    uri = f"ws://{HOST}:{PORT}"
    async with websockets.connect(uri) as ws:
        print("[station] connected")
        # Scenario toggles
        enc = (scenario != "weak_encryption")
        authed = (scenario != "unauthorized")
        fw_ver = "1.2.3" if scenario != "firmware_mismatch" else "0.9.0"

        # AUTH
        await ws.send(json.dumps({"type":"AUTH","payload":{"token": "demo-token" if authed else None}}))
        # Firmware
        await ws.send(json.dumps({"type":"FIRMWARE","payload":{"version": fw_ver}}))
        # START
        await ws.send(json.dumps({"type":"START","payload":{}}))

        energy = 0.0
        seq = 0
        base_voltage = 230.0
        base_current = 16.0  # ~3.6kW AC
        t0 = time.time()

        while True:
            seq += 1
            ts = now_ms()

            # normal jitter
            voltage = base_voltage + random.uniform(-3, 3)
            current = base_current + random.uniform(-1.5, 1.5)
            power_kw = max(0.0, voltage*current/1000.0)

            # Scenario injections
            if scenario == "power_spike" and seq == 6:
                power_kw = 40.0  # fiziksel olarak imkânsıza yakın pik
            if scenario == "non_monotonic_energy" and seq in (7, 8):
                energy -= 1.5  # geri gitme
            else:
                # normal enerji artışı
                energy += power_kw * 2.0/3600.0  # 2 sn aralık varsayımı

            payload = {
                "ts": ts if scenario != "timestamp_drift" else ts + (30000 if seq==5 else 0),
                "voltage": round(voltage,2),
                "current": round(current,2),
                "power_kw": round(power_kw,2),
                "energy_kwh": round(energy,3),
                "temp_c": round(28 + random.uniform(-1,2), 1),
                "enc": enc,
                "seq": seq
            }

            await ws.send(json.dumps({"type":"METRICS","payload": payload}))
            # Await response
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(resp)
                if data.get("type") == "CMD" and data.get("cmd") == "STOP_CHARGE":
                    print(f"[station] STOP received: {data.get('reason')}")
                    break
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(2.0 if scenario != "timestamp_drift" else (8.0 if seq==4 else 2.0))

        # STOP
        await ws.send(json.dumps({"type":"STOP","payload":{}}))
        print("[station] stopped")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="normal",
                    choices=["normal","power_spike","non_monotonic_energy","timestamp_drift","weak_encryption","unauthorized","firmware_mismatch"])
    args = ap.parse_args()
    asyncio.run(simulate(args.scenario))
