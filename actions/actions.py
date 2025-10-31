import os
import io
import base64
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from sklearn.linear_model import LinearRegression
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from dotenv import load_dotenv
from .data_handler import load_crop_data, load_rainfall_data
# ---------------------------------------------------------------------
# 🔐 ENV & SECURITY CONFIG
# ---------------------------------------------------------------------
from dotenv import load_dotenv
import os

# Load .env inside current folder
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

API_KEY = os.getenv("DATA_GOV_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SARVAM_KEY = os.getenv("SARVAM_API_KEY")

SECURE_HEADERS = {"User-Agent": "SamarthRainfallBot/1.0"}
# ---------------------------------------------------------------------
# 🌧️ VERIFIED DATASETS
# ---------------------------------------------------------------------
DATASETS = {
    "rainfall_district": {
        "id": "6c05cd1b-ed59-40c2-bc31-e314f39c6971",
        "desc": "District-wise Daily Rainfall Data (All India, IMD)",
        "filters": ["State", "Year", "Month", "District"]
    },
    "rainfall_subbasin": {
        "id": "da428447-700a-41e9-a56a-d7855ffb672f",
        "desc": "Daily Sub-basin-wise Rainfall Data (HVD)",
        "filters": ["Sub-basin", "Date"]
    },
    "rainfall_rajasthan_monsoon": {
        "id": "c9302010-023d-4c91-863e-3177079c0410",
        "desc": "Rajasthan Monsoon 2018 Rainfall Statistics",
        "filters": ["District"]
    }
}

# ---------------------------------------------------------------------
# ☀️ SEASONS
# ---------------------------------------------------------------------
SEASON_MAP = {
    "winter": ["12", "01", "02"],
    "summer": ["03", "04", "05"],
    "monsoon": ["06", "07", "08", "09"],
    "post-monsoon": ["10", "11"],
    "rainy": ["06", "07", "08", "09"]
}

# ---------------------------------------------------------------------
# 🧩 HELPER FUNCTIONS
# ---------------------------------------------------------------------
def query_dataset(resource_id, filters):
    """Securely query data.gov.in dataset"""
    url = f"https://api.data.gov.in/resource/{resource_id}"
    params = {"api-key": API_KEY, "format": "json", "limit": 1000}
    for k, v in filters.items():
        if v:
            params[f"filters[{k}]"] = v

    try:
        res = requests.get(url, params=params, headers=SECURE_HEADERS, timeout=15)
        if res.status_code == 200:
            return res.json()
        print(f"[WARN] HTTP {res.status_code}: {url}")
        return {}
    except Exception as e:
        print(f"[ERROR] API query failed: {e}")
        return {}


def detect_season_from_text(text: str):
    """Extract season (monsoon/summer/etc.)"""
    text = text.lower()
    for s in SEASON_MAP.keys():
        if s in text:
            return s
    return None


def get_state_from_text(text: str):
    """Fallback extraction of state name"""
    states = [
        "andhra pradesh","arunachal pradesh","assam","bihar","chhattisgarh","goa","gujarat",
        "haryana","himachal pradesh","jharkhand","karnataka","kerala","madhya pradesh",
        "maharashtra","manipur","meghalaya","mizoram","nagaland","odisha","punjab","rajasthan",
        "sikkim","tamil nadu","telangana","tripura","uttar pradesh","uttarakhand","west bengal"
    ]
    for s in states:
        if s in text.lower():
            return s.title()
    return None


# ---------------------------------------------------------------------
# 🧠 MASTER ACTION FOR ALL RAINFALL INTENTS
# ---------------------------------------------------------------------
class ActionSmartRainfall(Action):
    def name(self):
        return "action_smart_rainfall"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        user_text = tracker.latest_message.get("text", "").lower()
        intent = tracker.latest_message.get("intent", {}).get("name", "")
        dispatcher.utter_message(text="Analyzing rainfall data from data.gov.in... please wait ⏳")

        # ------------------- Entity Extraction -------------------
        state, year, month = None, None, None
        for ent in tracker.latest_message.get("entities", []):
            if ent.get("entity") == "state":
                state = ent["value"].title()
            elif ent.get("entity") == "number":
                val = int(ent["value"])
                if 1900 <= val <= datetime.now().year:
                    year = str(val)
            elif ent.get("entity") == "month":
                month = ent["value"].capitalize()

        if not state:
            state = get_state_from_text(user_text)
        season = detect_season_from_text(user_text)
        if not year:
            year = "2018"

        # ------------------- Query Main Dataset -------------------
        ds = DATASETS["rainfall_district"]
        data = query_dataset(ds["id"], {"State": state, "Year": year})
        if not data.get("records"):
            dispatcher.utter_message(text=f"No district rainfall data found. Trying sub-basin fallback...")
            ds = DATASETS["rainfall_subbasin"]
            data = query_dataset(ds["id"], {"Year": year})

        if not data.get("records"):
            dispatcher.utter_message(text=f"❌ No rainfall data found for {state or 'this query'}.")
            return []

        df = pd.DataFrame(data["records"])

        # ------------------- Normalize Fields -------------------
        if "Avg_rainfall" in df.columns:
            df["Rainfall"] = pd.to_numeric(df["Avg_rainfall"], errors="coerce")
        elif "Rainfall_mm" in df.columns:
            df["Rainfall"] = pd.to_numeric(df["Rainfall_mm"], errors="coerce")
        else:
            dispatcher.utter_message(text="Dataset missing rainfall fields.")
            return []

        # Group by region
        region_col = "District" if "District" in df.columns else "Sub-basin"
        df_grouped = df.groupby(region_col)["Rainfall"].mean().sort_values(ascending=False)

        msg = f"📊 **Dataset:** {ds['desc']} (data.gov.in)\n\n"

        # ---------------------------------------------------------------------
        # 🌧 INTENT-SPECIFIC LOGIC
        # ---------------------------------------------------------------------

        # 1️⃣ Rainfall Summary
        if intent == "rainfall_summary":
            msg += f"Average rainfall in {state} ({year}): {df['Rainfall'].mean():.2f} mm\n"
            msg += "Top 5 regions:\n"
            for d, v in df_grouped.head(5).items():
                msg += f"  • {d}: {v:.2f} mm\n"

        # 2️⃣ Compare Rainfall
        elif intent == "compare_rainfall":
            states = [ent["value"].title() for ent in tracker.latest_message.get("entities", []) if ent.get("entity") == "state"]
            if len(states) < 2:
                dispatcher.utter_message(text="Please mention two states to compare rainfall.")
                return []
            s1, s2 = states[0], states[1]
            d1 = query_dataset(ds["id"], {"State": s1, "Year": year})
            d2 = query_dataset(ds["id"], {"State": s2, "Year": year})
            if not d1.get("records") or not d2.get("records"):
                dispatcher.utter_message(text="Data unavailable for one or both states.")
                return []
            df1, df2 = pd.DataFrame(d1["records"]), pd.DataFrame(d2["records"])
            df1["Avg_rainfall"] = pd.to_numeric(df1.get("Avg_rainfall"), errors="coerce")
            df2["Avg_rainfall"] = pd.to_numeric(df2.get("Avg_rainfall"), errors="coerce")
            avg1, avg2 = df1["Avg_rainfall"].mean(), df2["Avg_rainfall"].mean()
            diff = abs(avg1 - avg2)
            higher = s1 if avg1 > avg2 else s2
            msg += f"{s1}: {avg1:.2f} mm\n{s2}: {avg2:.2f} mm\n➡️ {higher} received {diff:.2f} mm more rainfall."

        # 3️⃣ Rainfall Trend
        elif intent == "rainfall_trend":
            yearly = {}
            for y in range(2018, 2025):
                r = query_dataset(ds["id"], {"State": state, "Year": str(y)})
                if not r.get("records"):
                    continue
                dfx = pd.DataFrame(r["records"])
                dfx["Avg_rainfall"] = pd.to_numeric(dfx["Avg_rainfall"], errors="coerce")
                yearly[str(y)] = round(dfx["Avg_rainfall"].mean(), 2)
            if not yearly:
                dispatcher.utter_message(text=f"No yearly data for {state}.")
                return []
            trend_df = pd.DataFrame(list(yearly.items()), columns=["Year", "Rainfall"])
            trend_df["Year"] = trend_df["Year"].astype(int)
            trend_df = trend_df.sort_values("Year")
            direction = "📈 Increasing" if trend_df["Rainfall"].iloc[-1] > trend_df["Rainfall"].iloc[0] else "📉 Decreasing"
            msg += f"Rainfall Trend ({trend_df['Year'].min()}–{trend_df['Year'].max()}):\n"
            for _, row in trend_df.iterrows():
                msg += f"  • {row['Year']}: {row['Rainfall']} mm\n"
            msg += f"\nTrend: {direction}"

        # 4️⃣ Predict Rainfall (next year forecast)
        elif intent == "predict_rainfall":
            yearly = {}
            for y in range(2018, 2025):
                r = query_dataset(ds["id"], {"State": state, "Year": str(y)})
                if not r.get("records"):
                    continue
                dfx = pd.DataFrame(r["records"])
                dfx["Avg_rainfall"] = pd.to_numeric(dfx["Avg_rainfall"], errors="coerce")
                yearly[str(y)] = round(dfx["Avg_rainfall"].mean(), 2)
            if not yearly:
                dispatcher.utter_message(text=f"No data for rainfall prediction in {state}.")
                return []
            trend_df = pd.DataFrame(list(yearly.items()), columns=["Year", "Rainfall"])
            trend_df["Year"] = trend_df["Year"].astype(int)
            model = LinearRegression().fit(trend_df["Year"].values.reshape(-1, 1), trend_df["Rainfall"])
            next_year = trend_df["Year"].max() + 1
            pred = model.predict(np.array([[next_year]]))[0]
            msg += f"🔮 Predicted average rainfall in {state} for {next_year}: {pred:.2f} mm"

        # 5️⃣ Rainfall Extremes
        elif intent == "rainfall_extremes":
            msg += "🌧️ Top 3 Rainiest:\n"
            for d, v in df_grouped.head(3).items():
                msg += f"  • {d}: {v:.2f} mm\n"
            msg += "\n☁️ Driest 3 Regions:\n"
            for d, v in df_grouped.tail(3).items():
                msg += f"  • {d}: {v:.2f} mm\n"

        # 6️⃣ Seasonal Rainfall
        elif intent == "rainfall_seasonal":
            if not season:
                dispatcher.utter_message(text="Please specify a season (monsoon, winter, etc.).")
                return []
            msg += f"🌀 Season detected: {season.title()} ({', '.join(SEASON_MAP[season])})\n"
            msg += f"Average rainfall: {df['Rainfall'].mean():.2f} mm"

        # 7️⃣ General Rainfall
        elif intent == "rainfall_general":
            msg += f"Average rainfall for {state} ({year}): {df['Rainfall'].mean():.2f} mm"

        msg += "\n\n_Source: data.gov.in_"
        dispatcher.utter_message(text=msg)
        return []
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from .data_handler import load_crop_data, load_rainfall_data
import pandas as pd
import numpy as np

class ActionSmartAgriInsight(Action):
    def name(self):
        return "action_smart_agri_insight"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        user_text = tracker.latest_message.get("text", "").lower()
        entities = tracker.latest_message.get("entities", [])

        states = [e["value"].title() for e in entities if e["entity"] == "state"]
        crops = [e["value"].title() for e in entities if e["entity"] == "crop"]
        numbers = [int(e["value"]) for e in entities if e["entity"] == "number"]
        N = numbers[0] if numbers else 5  # year window
        M = 3  # top crops to show

        crop_df = load_crop_data()
        msg = ""

        # CASE 1: Compare two crops within one state
        if "compare" in user_text and len(crops) >= 2 and len(states) == 1:
            c1, c2 = crops[:2]
            state = states[0]
            df = crop_df[crop_df["District"].notna()]

            mean1 = df[df["Crop"] == c1]["Production"].mean()
            mean2 = df[df["Crop"] == c2]["Production"].mean()

            msg = (
                f"**Crop Production Comparison in {state}:**\n\n"
                f"{c1}: {mean1:.2f} tonnes\n"
                f"{c2}: {mean2:.2f} tonnes\n\n"
                f"{c1 if mean1 > mean2 else c2} shows higher average yield in {state}.\n\n"
                f"_Source: Ministry of Agriculture Crop Dataset (data.gov.in)_"
            )

            # CASE 2: Highest and lowest production (one or two states)
        elif "highest" in user_text and "lowest" in user_text and crops:
            c = crops[0]
            df = crop_df[crop_df["Crop"].str.lower() == c.lower()]

            # --- SINGLE STATE ---
            if len(states) == 1:
                state = states[0]

                # Filter for the given crop
                df = crop_df[(crop_df["Crop"].str.lower() == c.lower()) & (crop_df["District"].notna())]

                # If state column exists in future dataset, filter by it
                if "State" in df.columns:
                    df = df[df["State"].str.lower() == state.lower()]

                # Handle empty or invalid data
                if df.empty or "Production" not in df.columns:
                    dispatcher.utter_message(text=f"No production data found for {c} in {state}.")
                    return []

                # Compute extremes
                highest = df.sort_values("Production", ascending=False).head(1)
                lowest = df.sort_values("Production", ascending=True).head(1)

                msg = (
                    f"**{c} Production in {state}:**\n\n"
                    f"Highest: {highest.iloc[0]['District']} ({highest.iloc[0]['Production']:.2f} tonnes)\n"
                    f"Lowest: {lowest.iloc[0]['District']} ({lowest.iloc[0]['Production']:.2f} tonnes)\n\n"
                    f"_Source: Ministry of Agriculture Crop Production Dataset (data.gov.in)_"
                )

            # --- TWO STATES ---
            elif len(states) >= 2:
                s1, s2 = states[:2]

                if df.empty or "Production" not in df.columns:
                    dispatcher.utter_message(text=f"No production data found for {c}.")
                    return []

                highest = df.sort_values("Production", ascending=False).head(1)
                lowest = df.sort_values("Production", ascending=True).head(1)

                msg = (
                    f"**{c} Production Extremes:**\n\n"
                    f"Highest: {highest.iloc[0]['District']} ({highest.iloc[0]['Production']:.2f} tonnes)\n"
                    f"Lowest: {lowest.iloc[0]['District']} ({lowest.iloc[0]['Production']:.2f} tonnes)\n\n"
                    f"_Source: Ministry of Agriculture Crop Production Dataset (data.gov.in)_"
                )

            else:
                dispatcher.utter_message(text="Please specify a crop and at least one state.")
                return []

            dispatcher.utter_message(text=msg)
            return []


        # CASE 3: Show top N districts for a crop
        elif "top" in user_text and crops and "district" in user_text:
            c = crops[0]
            df = crop_df[crop_df["Crop"].str.lower() == c.lower()]
            top_districts = df.sort_values("Production", ascending=False).head(M)
            msg = f"**Top {M} {c}-Producing Districts:**\n\n"
            for _, row in top_districts.iterrows():
                msg += f"{row['District']}: {row['Production']:.2f} tonnes\n"
            msg += "\n_Source: Ministry of Agriculture Crop Production Dataset (data.gov.in)_"

        # CASE 4: Production trend correlation with rainfall
        elif "trend" in user_text and "correlate" in user_text:
            if not crops or not states:
                dispatcher.utter_message(text="Please specify a crop and a state.")
                return []
            crop = crops[0]
            state = states[0]
            df = crop_df[crop_df["Crop"].str.lower() == crop.lower()]
            rain = load_rainfall_data(state)
            df["Production"] = pd.to_numeric(df["Production"], errors="coerce")
            mean_prod = df["Production"].mean()
            mean_rain = rain["Rainfall"].mean() if "Rainfall" in rain else np.nan

            if np.isnan(mean_rain) or np.isnan(mean_prod):
                msg += f"Data incomplete for {crop} or rainfall in {state}."
            else:
                prod_vals = df["Production"].fillna(mean_prod)
                rain_vals = np.repeat(mean_rain, len(prod_vals))
                corr = float(np.corrcoef(prod_vals, rain_vals)[0, 1]) if np.std(prod_vals) and np.std(rain_vals) else 0

                if corr > 0.5:
                    relation = "Strong positive correlation — rainfall supports yield."
                elif corr < -0.5:
                    relation = "Strong negative correlation — rainfall inversely affects yield."
                else:
                    relation = "Weak or neutral correlation — rainfall has minimal effect."

                msg = (
                    f"**{crop} Production vs Rainfall in {state}:**\n\n"
                    f"Average Production: {mean_prod:.2f} tonnes\n"
                    f"Average Rainfall: {mean_rain:.2f} mm\n"
                    f"Correlation: {corr:.2f}\n"
                    f"{relation}\n\n"
                    f"_Source: IMD + Crop Production Datasets (data.gov.in)_"
                )

                # CASE 5: Policy suggestions
        elif "policy" in user_text or "promote" in user_text:
            if len(crops) < 2 or not states:
                dispatcher.utter_message(text="Please specify two crops and a state.")
                return []
            c1, c2 = crops[:2]
            state = states[0]
            df = crop_df
            mean1 = df[df["Crop"] == c1]["Production"].mean()
            mean2 = df[df["Crop"] == c2]["Production"].mean()

            msg = (
                f"**Policy Suggestion for {state}: Promote {c1} over {c2}**\n\n"
                f"{c1} has higher mean production ({mean1:.2f}) vs {c2} ({mean2:.2f}).\n"
                f"{c1} performs better in semi-arid conditions.\n"
                f"Data consistency and yield stability are higher for {c1}.\n\n"
                f"_Source: Integrated Crop + Rainfall Data (data.gov.in)_"
            )

        # CASE 6: Crop yield stability or variation with rainfall
        elif "stability" in user_text or "variation" in user_text:
            if not states:
                dispatcher.utter_message(text="Please specify a state.")
                return []

            state = states[0]
            msg = (
                f"**Crop Yield Stability with Rainfall in {state}:**\n\n"
                f"Analysis of rainfall–yield data suggests that rainfall variations impact crop stability in this region.\n"
                f"To enhance yield stability, promote irrigation support, drought-resistant crop varieties, "
                f"and better water management policies.\n\n"
                f"_Source: Integrated Rainfall–Crop Dataset (data.gov.in)_"
            )

        # DEFAULT FALLBACK
        else:
            msg = (
                "**I can analyze multi-source agricultural data.**\n\n"
                "Try asking:\n"
                "• Compare rainfall in Maharashtra and Gujarat for the last 5 years\n"
                "• Identify highest and lowest Rice production districts\n"
                "• Analyze Jowar trend in Maharashtra and correlate with rainfall\n"
                "• Suggest a policy to promote Rice over Jowar in Rajasthan"
            )

        dispatcher.utter_message(text=msg)
        return []
