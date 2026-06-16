import streamlit as st
import requests
import pandas as pd
import os
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Family World Cup Odds Tracker", layout="centered")

st.title("🏆 World Cup Quant Execution Agent")
st.markdown("---")

# 👤 INDIVIDUAL USER INITIALIZATION (Binds the private app deployment to the user)
st.sidebar.markdown("### 👤 User Identification")
user_input = st.sidebar.text_input("Enter your name to initialize profile:", value="").strip()

# Establish a clean fallback if the user hasn't typed a name yet
current_user = user_input if user_input else "Guest"
LEDGER_FILE = f"performance_ledger_{current_user.lower().replace(' ', '_')}.csv"

# API & Execution Configuration
API_KEY = "befc18bf0b281942ab3a946158bba14a" 
MIN_EDGE_THRESHOLD = 3.0

# 🧠 FIXED MATRIX: Pre-loaded live tournament ratings
ELO_DATABASE = {
    "France": 2050, "Argentina": 2110, "Norway": 1820, "Iran": 1780,
    "New Zealand": 1610, "Senegal": 1740, "Algeria": 1720, "Iraq": 1590,
    "Brazil": 2130, "England": 2040, "Spain": 2045, "Germany": 1960,
    "Netherlands": 1950, "Portugal": 1970, "Italy": 1940, "Belgium": 1910,
    "Croatia": 1890, "Uruguay": 1930, "Morocco": 1840, "Japan": 1850,
    "USA": 1790, "Mexico": 1780, "South Korea": 1775, "Australia": 1760,
    "Saudi Arabia": 1650, "Tunisia": 1710, "Poland": 1730, "Denmark": 1810
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
        # Structural check to guarantee columns line up perfectly
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
        return
    df = pd.read_csv(LEDGER_FILE)
    if df.empty or "PENDING" not in df["Status"].values:
        return
    results = fetch_live_results()
    if not results:
        return

    updated = False
    for idx, row in df.iterrows():
        if row["Status"] == "PENDING":
            match_data = next((m for m in results if f"{m.get('home_team')} vs. {m.get('away_team')}" == row["Match"]), None)
            if match_data and match_data.get("completed"):
                home_team = match_data.get("home_team")
                away_team = match_data.get("away_team")
                scores = match_data.get("scores", [])
                
                if scores:
                    h_score = int(next((s["score"] for s in scores if s["name"] == home_team), 0))
                    a_score = int(next((s["score"] for s in scores if s["name"] == away_team), 0))
                    
                    if h_score > a_score:
                        true_outcome = f"🏠 {home_team} Wins"
                    elif a_score > h_score:
                        true_outcome = f"✈️ {away_team} Wins"
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


# Run background clearing and load active database parameters
auto_clear_pending_positions()
ledger_df = load_ledger()

# 🗂️ TOP NAVIGATION TABS (Renamed to Results)
tab1, tab2 = st.tabs(["🚀 Active Market Analysis", "📊 Results"])

# ==========================================
# TAB 1: ACTIVE MARKET VIEW
# ==========================================
with tab1:
    if not user_input:
        st.warning("👈 Please input your name in the sidebar text box to lock in your tracking account session parameters.")
        
    st.subheader("Live Market Odds vs. ELO Predictive Signals")
    
    @st.cache_data(ttl=60)
    def fetch_live_world_cup_odds():
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=us,uk,eu,au&markets=h2h"
        try:
            response = requests.get(url, timeout=5.0)
            if response.status_code == 200: return response.json()
        except Exception: pass
        return []

    def normalize_team_name(name):
        mapping = {"USA": "United States", "South Korea": "Korea Republic"}
        return mapping.get(name, name)

    def calculate_elo_probabilities(home_team, away_team):
        home_norm = normalize_team_name(home_team)
        away_norm = normalize_team_name(away_team)
        r_home = ELO_DATABASE.get(home_norm, 1500)
        r_away = ELO_DATABASE.get(away_norm, 1500)
        exp_home = 1.0 / (1.0 + 10 ** ((r_away - r_home) / 400.0))
        exp_away = 1.0 / (1.0 + 10 ** ((r_home - r_away) / 400.0))
        draw_prob = 0.26
        return round(exp_home * (1 - draw_prob) * 100, 1), round(draw_prob * 100, 1), round(exp_away * (1 - draw_prob) * 100, 1), r_home, r_away

    def calculate_implied_probability(odds_val):
        try:
            odds = float(odds_val)
            return round((1.0 / odds) * 100, 1) if odds > 0 else 0
        except: return 0

    with st.spinner("Streaming metrics from live tournament feeds..."):
        games = fetch_live_world_cup_odds()

    if not games:
        st.info("No active data feeds returned. Verify network status or parameters.")
    else:
        if "last_logged_id" not in st.session_state: st.session_state.last_logged_id = None
        if "last_logged_time" not in st.session_state: st.session_state.last_logged_time = None

        if st.session_state.last_logged_id:
            c1, c2 = st.columns([3, 1])
            with c1: st.success(f"📦 Order successfully logged to private database profile under name: {current_user}!")
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
                        h_market_prob = calculate_implied_probability(h_odds)
                        a_market_prob = calculate_implied_probability(a_odds)
                        d_market_prob = calculate_implied_probability(d_odds)
                        
                        h_elo_prob, d_elo_prob, a_elo_prob, h_rating, a_rating = calculate_elo_probabilities(home_team, away_team)
                        home_edge, draw_edge, away_edge = round(h_elo_prob - h_market_prob, 1), round(d_elo_prob - d_market_prob, 1), round(a_elo_prob - a_market_prob, 1)
                        
                        st.markdown(f"### ⚽ {home_team} vs. {away_team}")
                        st.caption(f"📅 Kickoff: {kickoff} | 🧮 ELO Base: {home_team} ({int(h_rating)}) vs {away_team} ({int(a_rating)})")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1: st.metric(label=f"{home_team} (${h_odds:.2f})", value=f"ELO: {h_elo_prob}%", delta=f"{home_edge}% Edge")
                        with col2: st.metric(label=f"Draw (${d_odds:.2f})", value=f"ELO: {d_elo_prob}%", delta=f"{draw_edge}% Edge")
                        with col3: st.metric(label=f"{away_team} (${a_odds:.2f})", value=f"ELO: {a_elo_prob}%", delta=f"{away_edge}% Edge")
                        
                        execution_signals = []
                        if home_edge >= MIN_EDGE_THRESHOLD: execution_signals.append((f"🏠 {home_team} Wins", home_edge, h_odds))
                        if draw_edge >= MIN_EDGE_THRESHOLD: execution_signals.append(("🤝 Match Ends in a Draw", draw_edge, d_odds))
                        if away_edge >= MIN_EDGE_THRESHOLD: execution_signals.append((f"✈️ {away_team} Wins", away_edge, a_odds))
                        
                        if execution_signals:
                            st.markdown("#### 🤖 AGENT RECOMMENDATION: BUY")
                            for signal_name, edge_size, posted_odds in execution_signals:
                                suggested_stake = int(edge_size * 25)
                                st.info(f"**Target:** {signal_name} at **${posted_odds:.2f}** | *Calculated Stake:* **${suggested_stake} units**")
                                
                                button_id = f"exec_{home_team}_{away_team}_{posted_odds}".replace(" ", "_").lower()
                                if st.button(f"📥 Log Order to {current_user}'s Profile", key=button_id, disabled=not user_input):
                                    t_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    log_execution(match_title_string, signal_name, posted_odds, edge_size, suggested_stake, current_user)
                                    st.session_state.last_logged_id = button_id
                                    st.session_state.last_logged_time = t_stamp
                                    st.rerun()
                        else:
                            st.markdown("#### 🤖 AGENT RECOMMENDATION: HOLD")
                            st.caption("⚠️ Spreads tight. Position passed.")
                        st.markdown("---")

# ==========================================
# TAB 2: ISOLATED PRIVATE RESULTS DASHBOARD
# ==========================================
with tab2:
    st.subheader(f"📊 {current_user}'s Historical Results Matrix")
    
    if ledger_df.empty:
        st.info(f"No contract lines recorded yet. Enter your name and execute market edges to populate your private portfolio results array.")
    else:
        pending_df = ledger_df[ledger_df["Status"] == "PENDING"]
        settled_df = ledger_df[ledger_df["Status"] != "PENDING"]
        
        capital_at_risk = pending_df["Allocated Stake"].sum()
        total_net_earnings = round(ledger_df["Net Profit/Loss"].sum(), 2)
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric(label="Placed Contracts", value=len(ledger_df))
        with m_col2:
            st.metric(label="Active Capital At Risk", value=f"${capital_at_risk}")
        with m_col3:
            st.metric(
                label="Sum of Net Earnings (P&L)", 
                value=f"${total_net_earnings:+.2f}" if total_net_earnings != 0 else "$0.00",
                delta=f"{total_net_earnings:+.2f}" if total_net_earnings != 0 else None
            )
        
        st.markdown("### 📝 Itemized Statement of Profit & Loss")
        st.write(f"Showing the secure historical contract results line for **{current_user}**:")
        
        # Format strings into standard accounting layouts for the grid presentation layout
        display_df = ledger_df.copy()
        display_df["Execution Odds"] = display_df["Execution Odds"].map("${:.2f}".format)
        display_df["Allocated Stake"] = display_df["Allocated Stake"].map("${}".format)
        display_df["Return"] = display_df["Return"].map("${:.2f}".format)
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
            st.warning("Position successfully completely wiped from data logs.")
            st.rerun()