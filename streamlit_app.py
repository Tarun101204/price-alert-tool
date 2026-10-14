import streamlit as st
import tempfile
import os
import subprocess
import sys

st.set_page_config(page_title="Price Alert Tool", page_icon="📈", layout="wide")

st.title("📈 Price Alert Tool")
st.caption("Campus Assessment Build Brief - Wissen Technology")

sample_prices = """date,instrument,close
2026-09-01,INFY,1520.50
2026-09-01,TCS,3890.00
2026-09-02,INFY,1534.10
2026-09-02,TCS,3902.25
2026-09-03,INFY,1498.00"""

sample_rules = """[
  {
    "id": "r1",
    "instrument": "INFY",
    "type": "level",
    "direction": "below",
    "level": 1500
  },
  {
    "id": "r2",
    "instrument": "TCS",
    "type": "ma_cross",
    "short": 5,
    "long": 20,
    "direction": "above"
  }
]"""

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Prices CSV")
    prices_text = st.text_area("Prices CSV content (date,instrument,close)", value=sample_prices, height=220)

with col2:
    st.subheader("2. Rules JSON")
    rules_text = st.text_area("Rules JSON configuration", value=sample_rules, height=220)

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    run_btn = st.button("🚀 Run Alert Rules", type="primary", use_container_width=True)

if run_btn:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as pf:
        pf.write(prices_text)
        pf_name = pf.name
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as rf:
        rf.write(rules_text)
        rf_name = rf.name

    try:
        from alerts import process_alerts
        output_lines = process_alerts(pf_name, rf_name)
        st.subheader("Tool Output")
        if output_lines:
            st.code("\n".join(output_lines), language="text")
        else:
            st.info("No alerts fired on these trading days.")
    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        if os.path.exists(pf_name):
            os.remove(pf_name)
        if os.path.exists(rf_name):
            os.remove(rf_name)
