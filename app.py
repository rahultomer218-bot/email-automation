import base64
import json
import os
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from groq import Groq

# Page Layout Setup
st.set_page_config(page_title="Multi-Provider AI Email Automator", page_icon="✉️", layout="wide")

# Custom CSS for UI Cards & Branding Badges
st.markdown("""
    <style>
    .provider-badge {
        display: inline-block;
        padding: 8px 16px;
        margin: 5px;
        border-radius: 20px;
        font-weight: bold;
        color: white;
    }
    .google { background-color: #EA4335; }
    .yahoo { background-color: #6001D2; }
    .rediff { background-color: #D32F2F; }
    </style>
""", unsafe_allow_html=True)

# Main Title & Provider Badges
st.title("✉️ Smart Email Automator & Assistant")
st.markdown("""
<div>
    <span class="provider-badge google">🌐 Google / Gmail</span>
    <span class="provider-badge yahoo">🟣 Yahoo Mail</span>
    <span class="provider-badge rediff">🔴 Rediffmail</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# Environment Variables & Configurations
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
RESUME_PATH = "resume.pdf"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Session State Initializations
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""


# --- AUTHENTICATION & REGISTRATION SYSTEM ---
if not st.session_state.authenticated:
    st.subheader("🔐 User Login / Registration")
    
    tab1, tab2 = st.tabs(["Existing User Login", "New User Registration"])
    
    with tab1:
        login_email = st.text_input("Enter Registered Email:", key="login_email")
        login_btn = st.button("Login", type="primary")
        if login_btn:
            if login_email:
                st.session_state.authenticated = True
                st.session_state.user_email = login_email
                st.success(f"Welcome back, {login_email}!")
                st.rerun()
            else:
                st.error("Please enter a valid email address.")
                
    with tab2:
        reg_email = st.text_input("Enter Email to Register:", key="reg_email")
        provider = st.selectbox("Select Provider", ["Google / Gmail", "Yahoo Mail", "Rediffmail"])
        reg_btn = st.button("Register & Connect Account")
        if reg_btn:
            if reg_email:
                st.session_state.authenticated = True
                st.session_state.user_email = reg_email
                st.success(f"Account for {reg_email} ({provider}) registered and connected successfully!")
                st.rerun()
            else:
                st.error("Please fill all details.")

else:
    # --- LOGGED IN DASHBOARD & AUTOMATION CONTROL ---
    st.sidebar.success(f"Logged in as:\n**{st.session_state.user_email}**")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = ""
        st.rerun()

    st.subheader("⚙️ Automation Engine Dashboard")
    
    auto_run = st.checkbox("🔄 Enable Continuous Auto-Read Every 5 Minutes", value=True)
    
    def get_gmail_service():
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    st.error(f"Authentication refresh failed: {e}")
                    return None
            return build("gmail", "v1", credentials=creds)
        else:
            st.error("`token.json` file missing on server!")
            return None

    def classify_email(sender, subject, body):
        if not groq_client:
            return "OTHER"

        # Strictly filter out system emails, bounce messages, and marketing
        sender_lower = sender.lower()
        if any(x in sender_lower for x in ["mailer-daemon", "no-reply", "noreply", "matrimony", "render.com"]):
            return "OTHER"

        prompt = f"""
        You are a strict email filter. Analyze this email and classify it ONLY into:
        - JOB_OPPORTUNITY: Email MUST BE explicitly from a HR, Recruiter, or Hiring Manager about a job vacancy, interview call, or career proposal.
        - PROMOTIONAL: Ads, newsletters, transactional system emails, matrimonial alerts, marketing.
        - OTHER: Delivery failure notices, automated updates, receipts, non-job personal emails.

        Sender: {sender}
        Subject: {subject}
        Body: {body[:1000]}

        IMPORTANT: If it's an automated notification or system email, return OTHER.
        Return ONLY JSON: {{"category": "PROMOTIONAL" | "JOB_OPPORTUNITY" | "OTHER"}}
        """
        try:
            res = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            data = json.loads(res.choices[0].message.content)
            return data.get("category", "OTHER")
        except Exception:
            return "OTHER"

    def send_auto_reply(service, thread_id, to_email, original_subject):
        msg = MIMEMultipart()
        msg["To"] = to_email
        msg["Subject"] = f"Re: {original_subject}" if not original_subject.lower().startswith("re:") else original_subject
        body_text = "Hello,\n\nThank you for reaching out! Please find my attached resume.\n\nBest regards,\nRahul Tomer"
        msg.attach(MIMEText(body_text, "plain"))

        if os.path.exists(RESUME_PATH):
            with open(RESUME_PATH, "rb") as f:
                pdf = MIMEApplication(f.read(), _subtype="pdf")
                pdf.add_header("Content-Disposition", "attachment", filename="Rahul_Tomer_Resume.pdf")
                msg.attach(pdf)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        try:
            sent = service.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()
            st.success(f"✅ Resume sent to: **{to_email}** (Msg ID: {sent['id']})")
        except Exception as e:
            st.error(f"❌ Failed sending email to {to_email}: {e}")

    def execute_email_scan():
        service = get_gmail_service()
        if not service:
            return

        st.info(f"[{time.strftime('%H:%M:%S')}] Scanning unread messages for {st.session_state.user_email}...")
        results = service.users().messages().list(userId="me", q="is:unread in:inbox").execute()
        messages = results.get("messages", [])

        if not messages:
            st.write("No new unread messages.")
            return

        for msg_info in messages:
            msg = service.users().messages().get(userId="me", id=msg_info["id"], format="full").execute()
            headers = msg.get("payload", {}).get("headers", [])
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
            body = msg.get("snippet", "")

            cat = classify_email(sender, subject, body)
            st.markdown(f"📩 **Email:** `{subject}` | **From:** `{sender}` | **Category:** `{cat}`")

            if cat == "JOB_OPPORTUNITY":
                send_auto_reply(service, msg.get("threadId"), sender, subject)
                service.users().messages().batchModify(userId="me", body={"ids": [msg_info["id"]], "removeLabelIds": ["UNREAD"]}).execute()
            else:
                service.users().messages().batchModify(userId="me", body={"ids": [msg_info["id"]], "removeLabelIds": ["UNREAD"]}).execute()

    # Manual Trigger Button
    if st.button("🔍 Run Email Check Now"):
        execute_email_scan()

    # Automatic Loop (Every 5 minutes = 300 seconds)
    if auto_run:
        execute_email_scan()
        st.write("⏱️ Waiting for 5 minutes before next automatic check...")
        time.sleep(300)
        st.rerun()