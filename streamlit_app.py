import streamlit as st
import pandas as pd
import json, os, time
from pathlib import Path

st.set_page_config(page_title="EV Charge WS Monitor", layout="wide")
st.title("🔋 EV Charge — WebSocket Canlı İzleme")

DATA_FILE = Path(__file__).parent / "data" / "events.jsonl"
st.caption(f"Log: {DATA_FILE}")

st.sidebar.header("Canlı İzleme")
refresh_ms = st.sidebar.slider("Otomatik yenileme (ms)", 1000, 10000, 3000, step=500)
only_anomalies = st.sidebar.checkbox("Sadece anomalileri göster", value=False)
conn_filter = st.sidebar.text_input("Bağlantı filtresi (conn_id)")

st.sidebar.write("")
st.sidebar.write("**Durum:** çalışıyor ✅")
st.sidebar.write(time.strftime("🕒 %H:%M:%S"))

placeholder = st.empty()

def load_events():
    if not DATA_FILE.exists():
        return pd.DataFrame()
    rows = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except:
                pass
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # payload güvenliği
    if "payload" not in df.columns:
        df["payload"] = [{} for _ in range(len(df))]
    # payload alanları
    payload_cols = ["voltage","current","power_kw","energy_kwh","temp_c","seq","enc","ts"]
    for c in payload_cols:
        df[c] = df["payload"].apply(lambda d: d.get(c) if isinstance(d, dict) else None)
    # anomaly parse
    def codes(a):
        if isinstance(a, list):
            return ", ".join([str(x.get("code","")) for x in a if isinstance(x, dict)])
        return ""
    def sevs(a):
        if isinstance(a, list):
            return ", ".join([str(x.get("sev","")) for x in a if isinstance(x, dict)])
        return ""
    df["anomaly_codes"] = df.get("anomalies", pd.Series([None]*len(df))).apply(codes)
    df["sev_levels"] = df.get("anomalies", pd.Series([None]*len(df))).apply(sevs)
    df["ts_readable"] = pd.to_datetime(df["ts"], unit="s", errors="coerce")
    return df

# manuel yenileme döngüsü
while True:
    df = load_events()
    placeholder.empty()

    with placeholder.container():
        if df.empty:
            st.info("Henüz veri yok. `server.py` ve `station.py` çalıştığından emin olun.")
        else:
            if only_anomalies:
                df = df[df["anomaly_codes"].astype(str) != ""]
            if conn_filter.strip():
                try:
                    cid = int(conn_filter.strip())
                    df = df[df["conn_id"] == cid]
                except:
                    st.sidebar.error("conn_id sayı olmalı")

            # KPI
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Toplam Olay", len(df))
            col2.metric("Aktif Bağlantılar", df[df["type"].isin(["CONNECT"])]["conn_id"].nunique())
            col3.metric("Anomali Sayısı", (df["anomaly_codes"]!="").sum())
            col4.metric("STOP Komutu", (df.get("action","")=="STOP_CHARGE").sum())

            st.subheader("Son Olaylar")
            show_cols = ["ts_readable","conn_id","type","power_kw","energy_kwh",
                         "voltage","current","temp_c","anomaly_codes","sev_levels","action"]
            show_cols = [c for c in show_cols if c in df.columns]
            st.dataframe(df.sort_values("ts", ascending=False)[show_cols].head(200), use_container_width=True)

            st.subheader("Güç (kW) Zaman Serisi")
            chart_df = df[df["type"]=="METRICS"].sort_values("ts")
            if not chart_df.empty:
                st.line_chart(chart_df, x="ts_readable", y="power_kw")
            else:
                st.write("Grafik için veri yok.")

            st.subheader("Anomali Dağılımı (kod)")
            ac = (df["anomaly_codes"].str.split(", ").explode().value_counts())
            ac = ac[ac.index.notna() & (ac.index!="")]
            if not ac.empty:
                st.bar_chart(ac)
            else:
                st.write("Anomali yok.")

    time.sleep(refresh_ms/1000)
