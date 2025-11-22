from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class Anomaly:
    code: str
    message: str
    severity: str = "HIGH"  # "LOW" | "MEDIUM" | "HIGH"

class RuleEngine:
    def __init__(self):
        # Basit eşikler
        self.MAX_POWER_KW = 22.0    # AC istasyon nominal üst sınır
        self.MAX_CURRENT_A = 32.0
        self.VOLTAGE_RANGE = (190.0, 260.0)

        # Firmware beyaz liste
        self.ALLOWED_FW = {"1.2.3", "1.2.4"}

        # Durumsal ölçümler
        self._prev_energy = None
        self._prev_ts = None
        self._prev_seq = None

    # ---- Authentication ----
    def check_auth(self, payload: Dict[str, Any]):
        token = payload.get("token")
        if not token:
            return False, Anomaly("UNAUTHORIZED", "Kimlik doğrulama yok/bozuk", "HIGH")
        return True, None

    # ---- Firmware ----
    def check_firmware(self, payload: Dict[str, Any]):
        ver = payload.get("version")
        if ver not in self.ALLOWED_FW:
            return False, Anomaly("FIRMWARE_MISMATCH", f"Beklenmeyen firmware versiyonu: {ver}", "MEDIUM")
        return True, None

    # ---- Encryption (basit simülasyon) ----
    def check_encryption(self, payload: Dict[str, Any]) -> List[Anomaly]:
        enc = payload.get("enc", True)
        if not enc:
            return [Anomaly("WEAK_ENCRYPTION", "Veri şifrelenmemiş (simülasyon)", "LOW")]
        return []

    # ---- Metrics consistency ----
    def check_metrics(self, payload: Dict[str, Any], state) -> Optional[Anomaly]:
        ts = payload.get("ts")
        power_kw = payload.get("power_kw", 0.0)
        current = payload.get("current", 0.0)
        voltage = payload.get("voltage", 0.0)
        energy = payload.get("energy_kwh", 0.0)
        seq = payload.get("seq", 0)

        # 1) Fiziksel limitler
        if power_kw > self.MAX_POWER_KW * 1.2:
            return Anomaly("POWER_SPIKE", f"Güç {power_kw}kW limit üstünde", "HIGH")
        if current > self.MAX_CURRENT_A * 1.2:
            return Anomaly("CURRENT_SPIKE", f"Akım {current}A limit üstünde", "HIGH")
        if not (self.VOLTAGE_RANGE[0] <= voltage <= self.VOLTAGE_RANGE[1]):
            return Anomaly("VOLTAGE_OUT_OF_RANGE", f"Voltaj {voltage}V sınır dışı", "MEDIUM")

        # 2) Monotoniklik (kWh asla azalmamalı)
        if self._prev_energy is not None and energy < self._prev_energy - 1e-6:
            return Anomaly("NON_MONOTONIC_ENERGY", f"Energy {energy} < {self._prev_energy}", "HIGH")

        # 3) Zaman/sıra tutarlılığı (MitM/iletişim problemi simülasyonu)
        if self._prev_ts is not None and ts - self._prev_ts > 15000:
            return Anomaly("LATENCY_SPIKE", "Mesaj aralığı anormal (>15s)", "MEDIUM")
        if self._prev_seq is not None and seq != self._prev_seq + 1:
            return Anomaly("OUT_OF_ORDER", "Mesaj sırası bozuk", "MEDIUM")

        # Durumu güncelle
        self._prev_energy = energy
        self._prev_ts = ts
        self._prev_seq = seq
        return None
