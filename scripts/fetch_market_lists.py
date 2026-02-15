#!/usr/bin/env python3
"""
Fetch and update market ticker lists from Wikipedia and other sources.
"""

import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data" / "markets"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_sp500() -> list[str]:
    """Fetch S&P 500 tickers from Wikipedia."""
    print("📥 Fetching S&P 500...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
    return sorted(tickers)


def fetch_nasdaq100() -> list[str]:
    """Fetch NASDAQ 100 tickers from Wikipedia."""
    print("📥 Fetching NASDAQ 100...")
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url)
    # Find the table with tickers
    for df in tables:
        if 'Ticker' in df.columns:
            return sorted(df['Ticker'].tolist())
        if 'Symbol' in df.columns:
            return sorted(df['Symbol'].tolist())
    return []


def fetch_eurostoxx50() -> list[str]:
    """Fetch Euro Stoxx 50 tickers."""
    print("📥 Fetching Euro Stoxx 50...")
    url = "https://en.wikipedia.org/wiki/EURO_STOXX_50"
    tables = pd.read_html(url)
    for df in tables:
        if 'Ticker' in df.columns:
            return sorted(df['Ticker'].tolist())
    # Fallback: hardcoded list
    return [
        "ADS.DE", "AI.PA", "AIR.PA", "ALV.DE", "ASML.AS", "BAS.DE", "BAYN.DE", 
        "BBVA.MC", "BMW.DE", "BNP.PA", "CRH.L", "CS.PA", "DG.PA", "DHL.DE",
        "DTE.DE", "ENEL.MI", "ENGI.PA", "ENI.MI", "EL.PA", "FRE.DE",
        "IBE.MC", "IFX.DE", "ISP.MI", "ITX.MC", "KER.PA", "LIN.DE", "MC.PA",
        "MBG.DE", "MRK.DE", "MUV2.DE", "OR.PA", "ORA.PA", "PRX.AS", "RMS.PA",
        "RWE.DE", "SAN.MC", "SAN.PA", "SAP.DE", "SIE.DE", "STLA.PA", "SU.PA",
        "TEF.MC", "TTE.PA", "UCG.MI", "VNA.DE", "VOW3.DE"
    ]


def fetch_cac40() -> list[str]:
    """Fetch CAC 40 tickers."""
    print("📥 Fetching CAC 40...")
    url = "https://en.wikipedia.org/wiki/CAC_40"
    try:
        tables = pd.read_html(url)
        for df in tables:
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].tolist()
                return sorted([f"{t}.PA" if not t.endswith(".PA") else t for t in tickers])
    except:
        pass
    # Fallback
    return [
        "AI.PA", "AIR.PA", "ALO.PA", "ATO.PA", "BN.PA", "BNP.PA", "CAP.PA",
        "CS.PA", "DG.PA", "DSY.PA", "EL.PA", "ENGI.PA", "ERF.PA", "GLE.PA",
        "HO.PA", "KER.PA", "LR.PA", "MC.PA", "ML.PA", "MT.PA", "OR.PA",
        "ORA.PA", "PUB.PA", "RI.PA", "RMS.PA", "RNO.PA", "SAF.PA", "SAN.PA",
        "SGO.PA", "STLA.PA", "STM.PA", "SU.PA", "TEP.PA", "TTE.PA", "URW.PA",
        "VIE.PA", "VIV.PA", "WLN.PA"
    ]


def fetch_ftse_mib() -> list[str]:
    """Fetch FTSE MIB (Milan) tickers."""
    print("📥 Fetching FTSE MIB...")
    # Hardcoded - Italian market
    return [
        "A2A.MI", "AMP.MI", "AZM.MI", "BGN.MI", "BMED.MI", "BPE.MI", "BZU.MI",
        "CPR.MI", "DIA.MI", "ENEL.MI", "ENI.MI", "ERG.MI", "FBK.MI", "G.MI",
        "HER.MI", "IGD.MI", "IP.MI", "ISP.MI", "LDO.MI", "MB.MI", "MONC.MI",
        "NEXI.MI", "PIRC.MI", "PRY.MI", "PST.MI", "REC.MI", "RACE.MI", "SPM.MI",
        "SRG.MI", "STLA.MI", "TEN.MI", "TIT.MI", "TRN.MI", "UCG.MI", "UNI.MI"
    ]


def fetch_dax40() -> list[str]:
    """Fetch DAX 40 tickers."""
    print("📥 Fetching DAX 40...")
    return [
        "1COV.DE", "ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE",
        "BMW.DE", "CBK.DE", "CON.DE", "DB1.DE", "DBK.DE", "DHL.DE", "DTE.DE",
        "DTG.DE", "ENR.DE", "EON.DE", "FRE.DE", "HEI.DE", "HEN3.DE", "HFG.DE",
        "HNR1.DE", "IFX.DE", "LIN.DE", "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE",
        "PAH3.DE", "PUM.DE", "QIA.DE", "RHM.DE", "RWE.DE", "SAP.DE", "SHL.DE",
        "SIE.DE", "SY1.DE", "VNA.DE", "VOW3.DE", "ZAL.DE"
    ]


def fetch_ibex35() -> list[str]:
    """Fetch IBEX 35 tickers."""
    print("📥 Fetching IBEX 35...")
    return [
        "ACS.MC", "ACX.MC", "AENA.MC", "AMS.MC", "ANA.MC", "BBVA.MC", "BKT.MC",
        "CABK.MC", "CLNX.MC", "COL.MC", "ELE.MC", "ENG.MC", "FDR.MC", "FER.MC",
        "GRF.MC", "IAG.MC", "IBE.MC", "IDR.MC", "ITX.MC", "LOG.MC", "MAP.MC",
        "MEL.MC", "MRL.MC", "MTS.MC", "NTGY.MC", "RED.MC", "REP.MC", "ROVI.MC",
        "SAB.MC", "SAN.MC", "SCYR.MC", "SLR.MC", "TEF.MC", "UNI.MC", "VIS.MC"
    ]


def save_market(name: str, tickers: list[str], description: str = ""):
    """Save market tickers to JSON."""
    output_file = DATA_DIR / f"{name}.json"
    with open(output_file, "w") as f:
        json.dump({
            "name": name,
            "description": description,
            "updated_at": datetime.now().isoformat(),
            "count": len(tickers),
            "tickers": tickers
        }, f, indent=2)
    print(f"  ✅ Saved {len(tickers)} tickers to {output_file}")


def main():
    """Fetch all market lists."""
    print("🌍 Fetching market ticker lists...\n")
    
    markets = [
        ("sp500", fetch_sp500, "S&P 500 - US Large Cap"),
        ("nasdaq100", fetch_nasdaq100, "NASDAQ 100 - US Tech"),
        ("eurostoxx50", fetch_eurostoxx50, "Euro Stoxx 50 - European Blue Chips"),
        ("cac40", fetch_cac40, "CAC 40 - France"),
        ("ftse_mib", fetch_ftse_mib, "FTSE MIB - Italy"),
        ("dax40", fetch_dax40, "DAX 40 - Germany"),
        ("ibex35", fetch_ibex35, "IBEX 35 - Spain"),
    ]
    
    for name, fetcher, description in markets:
        try:
            tickers = fetcher()
            save_market(name, tickers, description)
        except Exception as e:
            print(f"  ❌ Error fetching {name}: {e}")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
