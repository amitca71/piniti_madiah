import altair as alt
import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import time

# --- 1. SETUP & AUTHENTICATION ---
def check_password():
    if "general" not in st.secrets:
        return True 

    def password_entered():
        if st.session_state["password"] == st.secrets["general"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("סיסמה", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("סיסמה", type="password", on_change=password_entered, key="password")
        st.error("😕 סיסמה שגויה")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gsheet_client():
    scope = [
        'https://www.googleapis.com/auth/spreadsheets', 
        'https://www.googleapis.com/auth/drive'
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def save_to_google_sheet(timestamp, day_of_week, name, activity):
    try:
        client = get_gsheet_client()
        # .sheet1 always targets the first tab
        sheet = client.open("piniti").sheet1
        sheet.insert_row([str(timestamp), day_of_week, name, activity], index=2, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"שגיאה בשמירה: {e}")
        return False

# NEW FUNCTION: Save to the Liars Sheet (Tab 2)
def save_liar_to_google_sheet(timestamp, day_of_week, name, activity):
    try:
        client = get_gsheet_client()
        # .get_worksheet(1) targets the SECOND tab from the left, regardless of its name
        sheet = client.open("piniti").get_worksheet(1)
        sheet.insert_row([str(timestamp), day_of_week, name, activity], index=2, value_input_option='USER_ENTERED')
        return True
    except Exception:
        # We don't want a liar-saving error to crash the main app, so we pass quietly
        return False

def get_data_from_sheet():
    try:
        client = get_gsheet_client()
        sheet = client.open("piniti").sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# NEW FUNCTION: Read from the Liars Sheet (Tab 2)
def get_liars_from_sheet():
    try:
        client = get_gsheet_client()
        sheet = client.open("piniti").get_worksheet(1)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# --- 3. DATA CONSTANTS & STATE ---
NAMES = ["YAFA", "SHIFSHUF", "LAKERD", "GAMAD", "GAMAL"]
ACTIVITIES = ["פינוי מדיח"] 
HEBREW_DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]

if 'is_saving' not in st.session_state:
    st.session_state.is_saving = False

def trigger_save():
    st.session_state.is_saving = True

# --- 4. UI START ---
st.markdown(
    "<h2 style='text-align:right; direction:rtl;'>🏠 ניהול מטלות הבית</h2>",
    unsafe_allow_html=True,
)

# Activity & Name Dropdowns
st.markdown("<div style='text-align:right; direction:rtl; margin-bottom:5px; font-size:18px;'>בחר/י מטלה:</div>", unsafe_allow_html=True)
selected_activity = st.selectbox("", ACTIVITIES, key="activity_select", label_visibility="collapsed")

st.markdown("<div style='text-align:right; direction:rtl; margin-bottom:5px; font-size:18px; margin-top:15px;'>מי ביצע/ה?</div>", unsafe_allow_html=True)
selected_name = st.selectbox("", NAMES, key="name_select", label_visibility="collapsed")

# --- SAVE BUTTON ---
st.markdown("<br>", unsafe_allow_html=True)

st.button(
    "💾 שמור נתונים" if not st.session_state.is_saving else "⏳ שומר...", 
    use_container_width=True, 
    type="primary", 
    on_click=trigger_save,
    disabled=st.session_state.is_saving
)

if st.session_state.is_saving:
    tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(tz)
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    today_str = now.strftime("%Y-%m-%d") 
    
    day_index = int(now.strftime("%w"))
    current_day = HEBREW_DAYS[day_index]
    
    df_check = get_data_from_sheet()
    already_reported = False
    
    if not df_check.empty and len(df_check.columns) >= 4:
        timestamp_col = df_check.columns[0]
        name_col = df_check.columns[2]
        activity_col = df_check.columns[3]
        
        df_check['JustDate'] = df_check[timestamp_col].astype(str).str[:10]
        
        match = df_check[(df_check[name_col] == selected_name) & 
                         (df_check[activity_col] == selected_activity) & 
                         (df_check['JustDate'] == today_str)]
        
        if not match.empty:
            already_reported = True

    if already_reported:
        # LOG THE LIAR TO SHEET 2
        save_liar_to_google_sheet(current_time, current_day, selected_name, selected_activity)
        
        st.error("דיווחת כבר, כרמלה מלשינה 🤦‍♂️")
        st.session_state.is_saving = False 
    else:
        if save_to_google_sheet(current_time, current_day, selected_name, selected_activity):
            st.success(f"✅ כל הכבוד {selected_name} על ביצוע: {selected_activity}! נשמר בהצלחה.")
            st.session_state.is_saving = False 
            time.sleep(1) 
            st.rerun() 
        else:
            st.error("❌ שגיאה בשמירה")
            st.session_state.is_saving = False 

# --- 5. HISTORY TABLE & LEADERBOARD ---
st.divider()
st.markdown("<h4 style='text-align:right; direction:rtl;'>📊 סטטיסטיקות והיסטוריה</h4>", unsafe_allow_html=True)

df = get_data_from_sheet()

if not df.empty and len(df.columns) >= 4:
    timestamp_col = df.columns[0]
    name_col = df.columns[2]
    activity_col = df.columns[3]
    
    filtered_df = df[df[activity_col] == selected_activity].copy()
    
    st.markdown("<div style='text-align:right; direction:rtl; font-weight:bold;'>סנן תקופת זמן:</div>", unsafe_allow_html=True)
    time_filter = st.radio(
        "", 
        ["כל הזמן", "3 ימים אחרונים", "שבוע אחרון", "חודש אחרון"], 
        horizontal=True, 
        label_visibility="collapsed"
    )
    
    if not filtered_df.empty:
        filtered_df['Datetime'] = pd.to_datetime(filtered_df[timestamp_col], format="%Y-%m-%d %H:%M:%S", errors='coerce')
        tz = pytz.timezone('Asia/Jerusalem')
        now_time = datetime.now(tz).replace(tzinfo=None) 
        
        if time_filter == "3 ימים אחרונים":
            cutoff = now_time - pd.Timedelta(days=3)
            filtered_df = filtered_df[filtered_df['Datetime'] >= cutoff]
        elif time_filter == "שבוע אחרון":
            cutoff = now_time - pd.Timedelta(days=7)
            filtered_df = filtered_df[filtered_df['Datetime'] >= cutoff]
        elif time_filter == "חודש אחרון":
            cutoff = now_time - pd.Timedelta(days=30)
            filtered_df = filtered_df[filtered_df['Datetime'] >= cutoff]

    if not filtered_df.empty:
        counts = filtered_df[name_col].value_counts().reset_index()
        counts.columns = ['שם', 'מספר פעמים']
        
        chart = alt.Chart(counts).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X('מספר פעמים:Q', title='כמות הפעמים שבוצע', axis=alt.Axis(tickMinStep=1, format='d')),
            y=alt.Y('שם:N', sort='-x', title=''),
            color=alt.Color('שם:N', legend=None),
            tooltip=['שם', 'מספר פעמים']
        ).properties(
            title=f'🏆 טבלת אלופים - {selected_activity} ({time_filter})',
            height=300
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info(f"אין נתונים עבור המטלה '{selected_activity}' בטווח הזמן הנבחר ({time_filter}).")

    
    st.markdown("<div style='text-align:right; direction:rtl;'><strong>10 הביצועים האחרונים (כל המטלות):</strong></div>", unsafe_allow_html=True)
    display_df = df.copy()
    if 'Datetime' in display_df.columns:
        display_df = display_df.drop(columns=['Datetime'])
    st.dataframe(display_df.head(10), use_container_width=True) 

else:
    st.info("אין נתונים או חסרות עמודות בטבלת הגוגל שיטס (נדרשות 4 עמודות).")

# --- 6. THE LIARS LIST (WALL OF SHAME) ---
st.divider()
st.markdown("<div style='text-align:right; direction:rtl;'>", unsafe_allow_html=True)
if st.toggle("🚨 הצג את רשימת השקרנים 🚨"):
    st.markdown("<h4 style='color:red;'>🤥 רשימת השקרנים</h4>", unsafe_allow_html=True)
    
    liars_df = get_liars_from_sheet()
    
    if not liars_df.empty:
        # Display the liars data
        st.dataframe(liars_df, use_container_width=True)
    else:
        st.success("כולם צדיקים! אין שקרנים בינתיים. 😇")
st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown(
    "<div style='text-align:right; direction:rtl; font-size:0.75rem; margin-top:2rem; color:gray;'>"
    "מופעל על ידי נאור סוכר בעמ"
    "</div>",
    unsafe_allow_html=True,
)
csv = df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 הורד נתונים (CSV)",
    data=csv,
    file_name='chores_log.csv',
    mime='text/csv',
)