import os, json, pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data_json")

def load_local_json(file_name):
    """Universal loader for data.gov.in JSONs (supports both 'records' and 'data' keys)."""
    path = os.path.join(DATA_DIR, file_name)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Case 1: Newer API export format
    if "records" in data:
        return pd.DataFrame(data["records"])

    # Case 2: Downloaded format with 'data' and 'fields'
    elif "data" in data and "fields" in data:
        # Extract column names from 'fields'
        columns = [field["id"] if isinstance(field, dict) else field for field in data["fields"]]
        df = pd.DataFrame(data["data"], columns=columns)
        return df

    # Case 3: List directly at root
    elif isinstance(data, list):
        return pd.DataFrame(data)

    else:
        raise ValueError(f"❌ Unsupported JSON format in {file_name}: keys={list(data.keys())}")

def load_crop_data():
    """Combine rice and jowar JSONs into one standardized DataFrame."""
    rice = load_local_json("rice.json")
    jowar = load_local_json("jowar.json")

    # Add crop labels
    rice["Crop"] = "Rice"
    jowar["Crop"] = "Jowar"

    # Rename dynamically
    rename_map = {
        "b": "District",
        "c": "Rainfed_Area",
        "d": "Irrigated_Area",
        "e": "Total_Area",
    }

    rice = rice.rename(columns=rename_map)
    jowar = jowar.rename(columns=rename_map)

    # Assign correct production columns per crop
    if "n" in rice.columns:
        rice.rename(columns={"n": "Production"}, inplace=True)
    elif "r" in rice.columns:
        rice.rename(columns={"r": "Production"}, inplace=True)

    if "r" in jowar.columns:
        jowar.rename(columns={"r": "Production"}, inplace=True)
    elif "n" in jowar.columns:
        jowar.rename(columns={"n": "Production"}, inplace=True)

    # Merge
    df = pd.concat([rice, jowar], ignore_index=True)

    # Clean types
    df["District"] = df["District"].astype(str).str.title()
    df["Production"] = pd.to_numeric(df["Production"], errors="coerce")

    return df


if __name__ == "__main__":
    print("🔍 Testing local dataset loader...")

    print("\n🌾 Combining rice + jowar data...")
    crop_df = load_crop_data()
    print("✅ Combined crop data shape:", crop_df.shape)
    print("Columns:", list(crop_df.columns))
    print(crop_df.head(5))

import requests

API_KEY = os.getenv("DATA_GOV_API_KEY", "579b464db66ec23bdd000001b0188e54573f48536618a7d6b4756b1e")
RAIN_DATASET_ID = "6c05cd1b-ed59-40c2-bc31-e314f39c6971"
SECURE_HEADERS = {"User-Agent": "SamarthRainfallBot/1.0"}

def query_rainfall_api(filters):
    """Query rainfall dataset via data.gov.in API."""
    url = f"https://api.data.gov.in/resource/{RAIN_DATASET_ID}"
    params = {"api-key": API_KEY, "format": "json", "limit": 1000}
    for k, v in filters.items():
        if v:
            params[f"filters[{k}]"] = v
    try:
        res = requests.get(url, params=params, headers=SECURE_HEADERS, timeout=15)
        if res.status_code == 200:
            return res.json()
        else:
            print(f"[WARN] HTTP {res.status_code} when fetching rainfall data.")
            return {}
    except Exception as e:
        print(f"[ERROR] Rainfall API failed: {e}")
        return {}

def load_rainfall_data(state: str = None, year: str = "2018"):
    """
    Load rainfall data for a given state and year from data.gov.in API.
    Falls back to local cache if API unavailable.
    """
    data = query_rainfall_api({"State": state, "Year": year}) if state else query_rainfall_api({"Year": year})

    if data.get("records"):
        df = pd.DataFrame(data["records"])
    else:
        # fallback: check for local rainfall cache
        cache_path = os.path.join(DATA_DIR, "rainfall_district.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            df = pd.DataFrame(cached.get("records", []))
        else:
            print("[WARN] No rainfall API data or local cache found.")
            return pd.DataFrame()

    # normalize columns
    if "Avg_rainfall" in df.columns:
        df["Rainfall"] = pd.to_numeric(df["Avg_rainfall"], errors="coerce")
    elif "Rainfall_mm" in df.columns:
        df["Rainfall"] = pd.to_numeric(df["Rainfall_mm"], errors="coerce")

    if "State" in df.columns:
        df["State"] = df["State"].astype(str).str.title()
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

    return df[["State", "Year", "Rainfall"]] if "Rainfall" in df.columns else df
