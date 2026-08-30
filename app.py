import os
import shutil
import subprocess
import sys
import streamlit as st

# Streamlit Page Config
st.set_page_config(
    page_title="AI Email Automator",
    page_icon="✉️",
    layout="centered"
)

# Pre-configured Groq Key (Hidden from User UI)
import os
from groq import Groq

# यह स्वचालित रूप से सर्वर या सिस्टम के Environment Variable से Key उठाएगा
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Custom CSS for UI styling
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 10px;
    }
    .status-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-top: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# Top Logo Header
st.markdown("""
    <div class="main-header">
        <img src="https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg" width="120" style="margin-bottom: 15px;">
        <h1>AI Gmail Assistant</h1>
        <p style="color: gray; font-size: 16px;">Automate your email job applications with AI precision</p>
    </div>
""", unsafe_allow_html=True)

st.divider()

# Section 1: Resume Management
st.subheader("📄 Resume Settings")
st.write("Upload your resume. If you upload a new one, it will automatically replace the existing one.")

uploaded_file = st.file_uploader("Upload or Update Resume (PDF)", type=["pdf"])

if uploaded_file is not None:
    # Save/Replace the resume as resume.pdf locally
    with open("resume.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"✅ Resume successfully updated: **{uploaded_file.name}**")
elif os.path.exists("resume.pdf"):
    st.info("ℹ️ Active Resume: **resume.pdf** is currently set for auto-replies.")
else:
    st.warning("⚠️ No resume found. Please upload a PDF resume to enable job auto-replies.")

st.divider()
# Section 3: Detailed Live Activity Log
st.subheader("📊 Live Activity & Email Log")

if os.path.exists("activity_log.txt"):
    with open("activity_log.txt", "r", encoding="utf-8") as log_file:
        logs = log_file.readlines()
        
    if logs:
        # Filter options
        filter_option = st.selectbox(
            "Filter History by Action:",
            ["All Activities", "Resumes Sent Only", "Trashed Emails Only"]
        )
        
        filtered_logs = logs
        if filter_option == "Resumes Sent Only":
            filtered_logs = [line for line in logs if "SENT RESUME" in line]
        elif filter_option == "Trashed Emails Only":
            filtered_logs = [line for line in logs if "TRASHED" in line]

        # Display latest logs on top
        st.text_area(
            label="Log Output (Latest Actions on Top)",
            value="".join(reversed(filtered_logs[-30:])),
            height=250
        )
    else:
        st.info("No activity logged yet.")
else:
    st.info("Activity log will appear here as soon as emails are processed.")
# Section 2: Automation Control Box
st.subheader("⚡ Automation Control")

col1, col2 = st.columns(2)

# Global Session State to track background process
if "process" not in st.session_state:
    st.session_state.process = None

with col1:
    if st.button("🚀 Start Automator", use_container_width=True, type="primary"):
        if not os.path.exists("resume.pdf"):
            st.error("Please upload a resume first!")
        elif st.session_state.process is None:
            # Start email_automator.py in background
            st.session_state.process = subprocess.Popen([sys.executable, "email_automator.py"])
            st.toast("Email Automator Started!", icon="✅")
        else:
            st.info("Automator is already running.")

with col2:
    if st.button("🛑 Stop Automator", use_container_width=True):
        if st.session_state.process is not None:
            st.session_state.process.terminate()
            st.session_state.process = None
            st.toast("Email Automator Stopped.", icon="🛑")
        else:
            st.info("Automator is not running.")

# Status Display
st.markdown("<br>", unsafe_allow_html=True)
if st.session_state.process is not None:
    st.success("🟢 **Status:** Active & Listening for incoming emails every 5 minutes...")
else:
    st.error("🔴 **Status:** Inactive (Click 'Start Automator' to launch)")

st.divider()

# Section 3: Live Logs Viewer
st.subheader("📊 Recent Activity Log")

if os.path.exists("activity_log.txt"):
    with open("activity_log.txt", "r", encoding="utf-8") as log_file:
        logs = log_file.readlines()
        if logs:
            st.text_area("Sent Resume History", "".join(reversed(logs[-15:])), height=200)
        else:
            st.write("No resumes sent yet.")
else:
    st.write("Activity log file will be generated once the first email is processed.")