import streamlit as st
import requests
import matplotlib.pyplot as plt
import pandas as pd
import time

# -----------------------------
# Streamlit Page Config
# -----------------------------
st.set_page_config(page_title="Samarth Rainfall Assistant (Under Production)", page_icon="💧", layout="wide")

# Backend RASA API
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"

# -----------------------------
# 🌈 Custom Styling
# -----------------------------
st.markdown("""
<style>
body, .stApp {
    background-color: #0E1117;
    color: #EAEAEA;
    font-family: 'Segoe UI', sans-serif;
}
.chat-bubble {
    padding: 12px 16px;
    border-radius: 16px;
    margin-bottom: 10px;
    line-height: 1.6;
    max-width: 80%;
    word-wrap: break-word;
}
.user-bubble {
    background-color: #007C60;
    color: white;
    margin-left: auto;
    text-align: right;
}
.bot-bubble {
    background-color: #1C1F26;
    color: #EAEAEA;
    margin-right: auto;
    border: 1px solid #2C2F36;
    text-align: left;
}
.bot-name { font-weight: 600; color: #62D9FB; }
.user-name { font-weight: 600; color: #A9DFBF; }
.stChatInput textarea {
    background-color: #1C1F26 !important;
    color: #EAEAEA !important;
}
.footer {
    color: #BFC9CA;
    font-size: 0.9em;
    text-align: center;
    margin-top: 20px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Cached Rasa Query
# -----------------------------
@st.cache_data(show_spinner=False)
def cached_query_rasa(user_message: str):
    try:
        res = requests.post(RASA_URL, json={"sender": "streamlit_user", "message": user_message})
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error querying Rasa: {e}")
    return None

# -----------------------------
# Chart Functions
# -----------------------------
def render_bar_chart(data: dict, title: str):
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(list(data.keys()), list(data.values()), color="#00FFB2", edgecolor="#00C48C", linewidth=1.5)
    ax.set_facecolor("#0E1117")
    fig.patch.set_facecolor("#0E1117")
    ax.tick_params(colors="white", labelsize=10)
    ax.set_ylabel("Rainfall (mm)", color="white", fontsize=11)
    ax.set_title(title, color="#62D9FB", fontsize=13, pad=10)
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

def render_line_chart_with_forecast(data: dict, title: str):
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig, ax = plt.subplots(figsize=(6, 3))
    df = pd.DataFrame(list(data.items()), columns=["Year", "Rainfall"])
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna().sort_values("Year")

    if df.empty:
        st.warning("No valid trend data available to display.")
        return

    ax.plot(df["Year"], df["Rainfall"], marker="o", linestyle="-", color="#62D9FB", linewidth=2, label="Actual")

    if len(df) > 1 and df["Year"].iloc[-1] - df["Year"].iloc[-2] == 1:
        ax.plot(
            [df["Year"].iloc[-2], df["Year"].iloc[-1]],
            [df["Rainfall"].iloc[-2], df["Rainfall"].iloc[-1]],
            linestyle="--", color="#00FFB2", label="Forecast"
        )

    ax.fill_between(df["Year"], df["Rainfall"], color="#62D9FB", alpha=0.15)
    ax.set_facecolor("#0E1117")
    fig.patch.set_facecolor("#0E1117")
    ax.tick_params(colors="white", labelsize=10)
    ax.set_ylabel("Rainfall (mm)", color="white", fontsize=11)
    ax.set_xlabel("Year", color="white", fontsize=11)
    ax.set_title(title, color="#62D9FB", fontsize=13, pad=10)
    ax.legend(facecolor="#1C1F26", edgecolor="#2C2F36", labelcolor="white")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

# -----------------------------
# Session State Initialization
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi, I'm **Samarth**, your rainfall intelligence assistant! Ask me about rainfall trends, comparisons, or forecasts."}
    ]

# -----------------------------
# Header
# -----------------------------
st.markdown("<h2 style='color:#62D9FB;'>Samarth Rainfall & Climate Assistant (Under Production)</h2>", unsafe_allow_html=True)

# -----------------------------
# Chat Input
# -----------------------------
user_input = st.chat_input("Type your message here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("🧠 Samarth is thinking..."):
        time.sleep(0.7)  # typing animation delay
        bot_responses = cached_query_rasa(user_input)

        if bot_responses:
            comparison_data, trend_data = {}, {}
            bot_message = ""

            for r in bot_responses:
                if "text" in r:
                    text = r["text"]
                    bot_message += text + "\n\n"

                    # Parse rainfall comparison (State: Value mm)
                    for line in text.splitlines():
                        line = line.strip()
                        if ":" in line and "mm" in line:
                            try:
                                region, val = line.split(":")[0].strip(), line.split(":")[1]
                                val = val.replace("mm", "").replace("➡️", "").strip()
                                if region and val.replace('.', '', 1).isdigit():
                                    if any(ch.isdigit() for ch in region):
                                        trend_data[int(''.join(ch for ch in region if ch.isdigit()))] = float(val)
                                    else:
                                        comparison_data[region] = float(val)
                            except:
                                continue

            st.session_state.messages.append({"role": "assistant", "content": bot_message})
        else:
            st.session_state.messages.append({"role": "assistant", "content": "Error: Unable to fetch data from backend."})

# -----------------------------
# Display Chat Conversation
# -----------------------------
for msg in st.session_state.messages:
    content_html = msg["content"].replace("\n", "<br>")
    if msg["role"] == "assistant":
        st.markdown(f"<div class='chat-bubble bot-bubble'><span class='bot-name'>Samarth:</span> {content_html}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble user-bubble'><span class='user-name'>You:</span> {content_html}</div>", unsafe_allow_html=True)

# -----------------------------
# Render Charts
# -----------------------------
if "comparison_data" in locals() and len(comparison_data) >= 2:
    st.markdown("<h4 style='color:#62D9FB;'>Rainfall Comparison Chart</h4>", unsafe_allow_html=True)
    render_bar_chart(comparison_data, "Rainfall Comparison (IMD Data)")
elif "trend_data" in locals() and len(trend_data) >= 2:
    st.markdown("<h4 style='color:#62D9FB;'>Rainfall Trend & Forecast</h4>", unsafe_allow_html=True)
    render_line_chart_with_forecast(trend_data, "Rainfall Trend & Forecast (IMD Data)")



# -----------------------------
# Footer
# -----------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("""
<div class="footer">
<b>Try asking these questions:</b><br><br>
<b>Note: It more of intent recognation based uses RASA so it might hallucinate</b><br><br>

<b>Rainfall Analysis:</b><br>
<code>Compare rainfall in Maharashtra and Gujarat</code><br>
<code>Show rainfall trend in Kerala</code><br>
<code>Predict rainfall for 2025 in Tamil Nadu</code><br>
<code>Which district got highest rainfall in Rajasthan?</code><br><br>

<b>Crop Insights:</b><br>
<code>Identify the district with highest Rice production and lowest in Gujarat</code><br>
<code>Show top 3 Rice-producing districts in Maharashtra</code><br>
<code>Compare Rice and Jowar production in Tamil Nadu</code><br><br>

<b>Correlation & Trends:</b><br>
<code>Analyze the production trend of Jowar in Maharashtra and correlate it with rainfall</code><br>
<code>Correlate annual rainfall with crop yield in Gujarat</code><br><br>

<b>Policy Suggestions:</b><br>
<code>Suggest a policy to promote Rice over Jowar in Rajasthan</code><br>
<code>Provide data-backed reasons to promote drought-resistant crops in Maharashtra</code><br><br>

<b>Multi-source Analysis:</b><br>
<code>Compare rainfall and top crops in Karnataka and Maharashtra</code><br>
<code>Analyze crop yield stability with respect to rainfall variations in Gujarat</code><br><br>

<b>General Queries:</b><br>
<code>What is Samarth?</code><br>
<code>Where do you get your rainfall data from?</code><br>
<code>What sources do you use for crop data?</code><br>
</div>
""", unsafe_allow_html=True)
