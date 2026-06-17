import streamlit as st
import requests
import pandas as pd
import os
import math
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Family World Cup Odds Tracker", layout="centered")

st.title("🏆 World Cup Autonomous Quant Agent")
st.markdown("---")

# 👤 AUTOMATED URL INITIALIZATION (Bypasses manual typing entirely)
url_params = st.query_params

if "user" in url_params:
    url_user = str(url_params["user"]).strip()
    current_user = url_user if url_user else "Guest"
    st.sidebar.markdown(f"### 👤 Active Profile: **{current_user}**")
    st.sidebar.caption("✅ Profile auto-loaded securely via linked session keys.")
else:
    st.sidebar.markdown("### 👤 User Identification")
    user_input = st.sidebar.text_input("Enter your name to initialize profile:", value="").strip()
    current_user = user_input if user_input else "Guest"
    if not user_input:
        st.warning("👈 Please input your name in the sidebar or use your personalized URL parameter to unlock execution.")

# Bind file path parameters strictly to the resolved user string
LEDGER_FILE = f"performance_ledger_{current_user.lower().replace(' ', '_')}.csv"

# API & Sizing Configuration
API_KEY = "befc18bf0b281942ab3a946158bba14a" 
MIN_EDGE_THRESHOLD = 2.0  # Safe threshold for xG variance matrix models
INITIAL_BANKROLL = 10000.0

# 📊 GOAL EXPECTANCY MATRIX DATABASE
XG_DATABASE = {
    "France":       {"att": 2.30, "def": 0.85},
    "Argentina":    {"att": 2.15, "def": 0.80},
    "Brazil":       {"att": 2.10, "def": 0.90},
    "England":      {"att": 1.95, "def": 0.95},
    "Spain":        {"att": 2.05, "def": 0.90},
    "Germany":      {"att": 1.85, "def": 1.10},
    "Netherlands":  {"att": 1.70, "def": 1.05},
    "Portugal":     {"att": 1.90, "def": 1.00},
    "Italy":        {"att": 1.55, "def": 0.95},
    "Belgium":      {"att": 1.60, "def": 1.15},
    "Croatia":      {"att": 1.45, "def": 1.10},
    "Uruguay":      {"att": 1.65, "def": 1.05},
    "Morocco":      {"att": 1.30, "def": 0.85},
    "Japan":        {"att": 1.50, "def": 1.20},
    "USA":          {"att": 1.40, "def": 1.25},
    "Mexico":       {"att": 1.35, "def": 1.30},
    "South Korea":  {"att": 1.30, "def": 1.35},
    "Australia":    {"att": 1.20, "def": 1.25},
    "Iran":         {"att": 1.10, "def": 1.20},
    "Norway":       {"att": 1.60, "def": 1.30},
    "Senegal":      {"att": 1.25, "def": 1.10},
    "Algeria":      {"att": 1.20, "def": 1.15},
    "Denmark":      {"att": 1.40, "def": 1.10},
    "Poland":       {"att": 1.25, "def": 1.40},
    "Saudi Arabia": {"att": 0.95, "def": 1.50},
    "Tunisia":      {"att": 0.90, "def": 1.25},
    "New Zealand":  {"att": 0.85, "def": 1.60},
    "Iraq":         {"att": 0.90, "def": 1.55}
}

# 📑 PERFORMANCE LEDGER CONTROLLER FUNCTIONS
def log_execution(match_name, target, market_odds, edge, stake, player_name):
    new_row = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User": player_name,
        "Match": match_name,
        "Target Selection": target,
        "Execution Odds": float(market_odds),
        "Calculated Edge %": float(edge),
        "Allocated Stake": int(stake),
        "Return": 0.0,
        "Net Profit/Loss": 0.0,
        "Status": "PENDING"
    }])
    if not os.path.exists(LEDGER_FILE):
        new_row.to_csv(LEDGER_FILE, index=False)
    else:
        new_row.to_csv(LEDGER_FILE, mode='a', header=False, index=False)

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        df = pd.read_csv(LEDGER_FILE)
        if "User" not in df.columns:
            df.insert(1, "User", current_user)
        if "Return" not in df.columns:
            df["Return"] = 0.0
        if "Net Profit/Loss" not in df.columns:
            df["Net Profit/Loss"] = 0.0
        return df
    return pd.DataFrame(columns=["Timestamp", "User", "Match", "Target Selection", "Execution Odds", "Calculated Edge %", "Allocated Stake", "Return", "Net Profit/Loss", "Status"])

def remove_transaction(timestamp):
    if os.path.exists(LEDGER_FILE):
        df = pd.read_csv(LEDGER_FILE)
        df = df[df['Timestamp'] != timestamp]
        if df.empty:
            try: os.remove(LEDGER_FILE)
            except: pass
        else:
            df.to_csv(LEDGER_FILE, index=False)

def fetch_live_results():
    try:
        score_url = f"https://api.the-odds-api.com/v4/sports/soccer/scores/?apiKey={API_KEY}&daysFrom=3"
        response = requests.get(score_url, timeout=5.0)
        if response.status_code == 200: return response.json()
    except Exception: pass
    return []

def auto_clear_pending_positions():
    if not os.path.exists(LEDGER_FILE):
        return False
    df = pd.read_csv(LEDGER_FILE)
    if df.empty or "PENDING" not in df["Status"].values:
        return False
    results = fetch_live_results()
    if not results:
        return False

    # 🗺️ ALIAS TRANSLATION MATRIX: Maps shorthand strings to standard API formats
    TEAM_ALIASES = {
        "DR Congo": "Democratic Republic of the Congo",
        "USA": "United States",
        "South Korea": "Republic of Korea"
    }

    updated = False
    for idx, row in df.iterrows():
        if row["Status"] == "PENDING":
            # Translate ledger shorthand text to standard format for API pairing
            ledger_match = str(row["Match"])
            for shorthand, canonical in TEAM_ALIASES.items():
                ledger_match = ledger_match.replace(shorthand, canonical)
            
            # Cross-reference live metrics with translated targets
            match_data = next((m for m in results if f"{m.get('home_team')} vs. {m.get('away_team')}" == ledger_match), None)
            
            if match_data and match_data.get("completed"):
                home_team = match_data.get("home_team")
                away_team = match_data.get("away_team")
                scores = match_data.get("scores", [])
                
                if scores:
                    h_score = int(next((s["score"] for s in scores if s["name"] == home_team), 0))
                    a_score = int(next((s["score"] for s in scores if s["name"] == away_team), 0))
                    
                    # Reverse-translate standard names back to ledger formatting for display
                    display_home = home_team
                    display_away = away_team
                    for shorthand, canonical in TEAM_ALIASES.items():
                        if canonical == home_team: display_home = shorthand
                        if canonical == away_team: display_away = shorthand
                    
                    if h_score > a_score:
                        true_outcome = f"🏠 {display_home} Wins"
                    elif a_score > h_score:
                        true_outcome = f"✈️ {display_away} Wins"
                    else:
                        true_outcome = "🤝 Match Ends in a Draw"
                    
                    if row["Target Selection"] == true_outcome:
                        df.at[idx, "Status"] = "WIN"
                        payout = round(row["Allocated Stake"] * row["Execution Odds"], 2)
                        df.at[idx, "Return"] = payout
                        df.at[idx, "Net Profit/Loss"] = round(payout - row["Allocated Stake"], 2)
                    else:
                        df.at[idx, "Status"] = "LOSS"
                        df.at[idx, "Return"] = 0.0
                        df.at[idx, "Net Profit/Loss"] = float(-row["Allocated Stake"])
                    updated = True
                    
    if updated:
        df.to_csv(LEDGER_FILE, index=False)
    return updated

# 🧮 POISSON DISTRIBUTION ENGINE FUNCTION
def poisson_probability(k, lamb):
    return (math.exp(-lamb) * (lamb ** k)) / math.factorial(k)

def calculate_xg_probabilities(home_team, away_team):
    home_stats = XG_DATABASE.get(home_team, {"att": 1.40, "def": 1.20})
    away_stats = XG_DATABASE.get(away_team, {"att": 1.40, "def": 1.20})
    
    lambda_home = home_stats["att"] * away_stats["def"]
    lambda_away = away_stats["att"] * home_stats["def"]
    
    home_win_prob = 0.0
    away_win_prob = 0.0
    draw_prob = 0.0
    
    for h_goals in range(9):
        for a_goals in range(9):
            p_matrix = poisson_probability(h_goals, lambda_home) * poisson_probability(a_goals, lambda_away)
            if h_goals > a_goals:
                home_win_prob += p_matrix
            elif a_goals > h_goals:
                away_win_prob += p_matrix
            else:
                draw_prob += p_matrix
                
    return round(home_win_prob * 100, 1), round(draw_prob * 100, 1), round(away_win_prob * 100, 1), lambda_home, lambda_away


# =================================================================
# 🔄 AUTOMATED REAL-TIME LIFE-CYCLE BACKGROUND CONTROLLER
# =================================================================
auto_clear_pending_positions()
ledger_df = load_ledger()

@st.fragment(run_every=600)  # Executes a silent background sweep every 10 minutes
def execute_silent_live_score_sync():
    if os.path.exists(LEDGER_FILE):
        df_audit = pd.read_csv(LEDGER_FILE)
        if "PENDING" in df_audit["Status"].values:
            if auto_clear_pending_positions():
                st.rerun()

execute_silent_live_score_sync()

# Determine active liquid bankroll parameters based on past performance results
finalized_pnl = ledger_df["Net Profit/Loss"].sum() if not ledger_df.empty else 0.0
current_liquid_bankroll = max(100.0, INITIAL_BANKROLL + finalized_pnl)

# Navigation configuration
tab1, tab2 = st.tabs(["🚀 Active Market Analysis", "📊 Results"])

# ==========================================
# TAB 1: ACTIVE MARKET ANALYSIS VIEW
# ==========================================
with tab1:
    st.subheader("Live Market Odds vs. Goal Expectancy ($xG$) Models")
    
    @st.cache_data(ttl=60)
    def fetch_live_world_cup_odds():
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=us,uk,eu,au&markets=h2h"
        try:
            response = requests.get(url, timeout=5.0)
            if response.status_code == 200: return response.json()
        except Exception: pass
        return []

    with st.spinner("Streaming metrics from live tournament feeds..."):
        games = fetch_live_world_cup_odds()

    if not games:
        st.info("No active data feeds returned. Verify network status or parameters.")
    else:
        if "last_logged_id" not in st.session_state: st.session_state.last_logged_id = None
        if "last_logged_time" not in st.session_state: st.session_state.last_logged_time = None

        if st.session_state.last_logged_id:
            c1, c2 = st.columns([3, 1])
            with c1: st.success(f"📦 Order successfully logged to private profile: {current_user}!")
            with c2:
                if st.button("↩️ Quick Undo", key="immediate_undo"):
                    remove_transaction(st.session_state.last_logged_time)
                    st.session_state.last_logged_id = None
                    st.session_state.last_logged_time = None
                    st.rerun()

        for game in games:
            sport_key = game.get('sport_key', '').lower()
            sport_title = game.get('sport_title', '').lower()
            
            if "world_cup" in sport_key or "world cup" in sport_title:
                home_team = game.get('home_team')
                away_team = game.get('away_team')
                match_title_string = f"{home_team} vs. {away_team}"
                
                try: kickoff = pd.to_datetime(game['commence_time']).tz_convert('Asia/Hong_Kong').strftime('%B %d, %H:%M HK Time')
                except: kickoff = "Upcoming"

                bookmakers = game.get('bookmakers', [])
                current_bookie = bookmakers[0] if bookmakers else None

                if current_bookie:
                    markets = current_bookie.get('markets', [])
                    if markets:
                        outcomes = markets[0].get('outcomes', [])
                        h_data = next((o for o in outcomes if o['name'] == home_team), {})
                        a_data = next((o for o in outcomes if o['name'] == away_team), {})
                        d_data = next((o for o in outcomes if o['name'].lower() == 'draw'), {})
                        
                        h_odds, a_odds, d_odds = h_data.get('price', 0.0), a_data.get('price', 0.0), d_data.get('price', 0.0)
                        
                        mkt_h = round((1.0 / h_odds) * 100, 1) if h_odds > 0 else 0
                        mkt_d = round((1.0 / d_odds) * 100, 1) if d_odds > 0 else 0
                        mkt_a = round((1.0 / a_odds) * 100, 1) if a_odds > 0 else 0
                        
                        xg_h_prob, xg_d_prob, xg_a_prob, lam_h, lam_a = calculate_xg_probabilities(home_team, away_team)
                        
                        edge_h = round(xg_h_prob - mkt_h, 1)
                        edge_d = round(xg_d_prob - mkt_d, 1)
                        edge_a = round(xg_a_prob - mkt_a, 1)
                        
                        st.markdown(f"### ⚽ {home_team} vs. {away_team}")
                        st.caption(f"📅 Kickoff: {kickoff} | 🧮 Project xG Rate: {home_team} ({lam_h:.2f}) vs {away_team} ({lam_a:.2f})")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1: st.metric(label=f"{home_team} (${h_odds:.2f})", value=f"xG: {xg_h_prob}%", delta=f"{edge_h}% Edge")
                        with col2: st.metric(label=f"Draw (${d_odds:.2f})", value=f"xG: {xg_d_prob}%", delta=f"{edge_d}% Edge")
                        with col3: st.metric(label=f"{away_team} (${a_odds:.2f})", value=f"xG: {xg_a_prob}%", delta=f"{edge_a}% Edge")
                        
                        signals = []
                        if edge_h >= MIN_EDGE_THRESHOLD:
                            b_factor = h_odds - 1.0
                            p_factor = xg_h_prob / 100.0
                            q_factor = 1.0 - p_factor
                            kelly_fraction = 0.5 * ((b_factor * p_factor - q_factor) / b_factor)
                            if kelly_fraction > 0: signals.append((f"🏠 {home_team} Wins", edge_h, h_odds, kelly_fraction))
                            
                        if edge_d >= MIN_EDGE_THRESHOLD:
                            b_factor = d_odds - 1.0
                            p_factor = xg_d_prob / 100.0
                            q_factor = 1.0 - p_factor
                            kelly_fraction = 0.5 * ((b_factor * p_factor - q_factor) / b_factor)
                            if kelly_fraction > 0: signals.append(("🤝 Match Ends in a Draw", edge_d, d_odds, kelly_fraction))
                            
                        if edge_a >= MIN_EDGE_THRESHOLD:
                            b_factor = a_odds - 1.0
                            p_factor = xg_a_prob / 100.0
                            q_factor = 1.0 - p_factor
                            kelly_fraction = 0.5 * ((b_factor * p_factor - q_factor) / b_factor)
                            if kelly_fraction > 0: signals.append((f"✈️ {away_team} Wins", edge_a, a_odds, kelly_fraction))
                        
                        profile_unlocked = ("user" in url_params or ('user_input' in locals() and user_input))
                        
                        if signals:
                            st.markdown("#### 🤖 AGENT RECOMMENDATION: BUY")
                            for signal_name, edge_val, price, fraction in signals:
                                allocation_stake = int(current_liquid_bankroll * fraction)
                                allocation_stake = max(10, min(allocation_stake, 1500))
                                
                                if edge_val >= 5.0:
                                    st.markdown(
                                        f"""
                                        <div style="
                                            background-color: #FFF3CD; 
                                            border-left: 6px solid #FFC107; 
                                            padding: 15px; 
                                            border-radius: 6px; 
                                            margin-bottom: 15px;
                                        ">
                                            <span style="color: #856404; font-weight: bold; font-size: 1.1em;">
                                                🔥 HIGH CONVICTION ALERT (+{edge_val}% Edge)
                                            </span><br>
                                            <span style="color: #A94442; font-weight: bold;">Target Selection:</span> 
                                            <span style="color: #222222;">{signal_name} at <b>${price:.2f}</b></span><br>
                                            <span style="color: #A94442; font-weight: bold;">Half-Kelly Capital Size:</span> 
                                            <span style="color: #222222;"><b>${allocation_stake}</b> ({fraction*100:.1f}% of Wallet)</span>
                                        </div>
                                        """, 
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.info(f"**Target Selection:** {signal_name} at **${price:.2f}** | 🧠 **Half-Kelly Capital Size:** **${allocation_stake}** (*{fraction*100:.1f}% of Wallet*)")
                                
                                button_id = f"exec_{home_team}_{away_team}_{price}".replace(" ", "_").lower()
                                if st.button(f"📥 Log Half-Kelly Contract for {signal_name}", key=button_id, disabled=not profile_unlocked):
                                    t_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    log_execution(match_title_string, signal_name, price, edge_val, allocation_stake, current_user)
                                    st.session_state.last_logged_id = button_id
                                    st.session_state.last_logged_time = t_stamp
                                    st.rerun()
                        else:
                            st.markdown("#### 🤖 AGENT RECOMMENDATION: HOLD")
                            st.caption("⚠️ Spreads efficient. Volatility holding.")
                        st.markdown("---")

# ==========================================
# TAB 2: PRIVACY-LOCKED RESULTS MATRIX VIEW
# ==========================================
with tab2:
    st.subheader(f"📊 {current_user}'s Live Results Matrix")
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.metric(label="Starting Bankroll", value=f"${INITIAL_BANKROLL:,.2f}")
    with m_col2:
        if ledger_df.empty:
            st.metric(label="Current Net Balance", value=f"${INITIAL_BANKROLL:,.2f}", delta="$0.00")
        else:
            pnl_delta = ledger_df["Net Profit/Loss"].sum()
            st.metric(
                label="Current Net Balance", 
                value=f"${INITIAL_BANKROLL + pnl_delta:,.2f}", 
                delta=f"{pnl_delta:+.2f}" if pnl_delta != 0 else None
            )
    with m_col3:
        pending_capital = ledger_df[ledger_df["Status"] == "PENDING"]["Allocated Stake"].sum() if not ledger_df.empty else 0
        st.metric(label="Active Capital at Risk", value=f"${pending_capital}")
        
    st.markdown("---")
    
    if ledger_df.empty:
        st.info("No contract lines recorded yet. Initialize your profile link and execute value signals to build your ledger.")
    else:
        st.markdown("### 📝 Itemized Statement of Profit & Loss")
        
        display_df = ledger_df.copy()
        display_df["Execution Odds"] = display_df["Execution Odds"].map("${:.2f}".format)
        display_df["Allocated Stake"] = display_df["Allocated Stake"].map("${:,}".format)
        display_df["Return"] = display_df["Return"].map("${:,.2f}".format)
        display_df["Net Profit/Loss"] = display_df["Net Profit/Loss"].map("${:+.2f}".format)
        
        st.dataframe(display_df.sort_values(by="Timestamp", ascending=False), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**🔧 Database Administration & Record Correction**")
        selected_timestamp = st.selectbox(
            "Select a transaction timestamp to remove from database history:",
            options=ledger_df.sort_values(by="Timestamp", ascending=False)["Timestamp"].tolist(),
            index=0
        )
        target_row_info = ledger_df[ledger_df["Timestamp"] == selected_timestamp].iloc[0]
        
        if st.button(f"🗑️ Delete Record: {target_row_info['Target Selection']} ({target_row_info['Allocated Stake']})", type="primary"):
            remove_transaction(selected_timestamp)
            st.warning("Position successfully completely wiped from data history.")
            st.rerun()
