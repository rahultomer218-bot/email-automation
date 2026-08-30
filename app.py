import base64
import json
import os
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from groq import Groq

# --- CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  
RESUME_PATH = "resume.pdf"
POLL_INTERVAL_SECONDS = 30  # Har 30 seconds me check karega

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

groq_client = Groq(api_key=GROQ_API_KEY)


def get_gmail_service():
    """Authenticates the user and returns the Gmail API service object."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Error: token.json missing or invalid on server.")
            return None

    return build("gmail", "v1", credentials=creds)


def classify_email(sender, subject, body):
    """Uses Groq API to categorize the email into strict JSON."""
    prompt = f"""
    Analyze the following email and classify it into EXACTLY ONE category:
    - PROMOTIONAL (Spam, newsletters, marketing, ads, discounts)
    - JOB_OPPORTUNITY (Recruiters, interview calls, job offers, career inquiries)
    - OTHER (Personal emails, transactional receipts, general notifications)

    Sender: {sender}
    Subject: {subject}
    Body: {body[:1000]}

    Return ONLY a JSON object in this exact format, with no additional text:
    {{"category": "PROMOTIONAL" | "JOB_OPPORTUNITY" | "OTHER"}}
    """

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Correct Active Groq Model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("category", "OTHER")
    except Exception as e:
        print(f"Error classifying email with AI: {e}")
        return "OTHER"


def send_auto_reply(service, thread_id, to_email, original_subject):
    """Sends an automated reply email with the resume PDF attached and logs the result."""
    message = MIMEMultipart()
    message["To"] = to_email
    message["Subject"] = (
        f"Re: {original_subject}"
        if not original_subject.lower().startswith("re:")
        else original_subject
    )

    body_text = (
        "Hello,\n\n"
        "Thank you for reaching out regarding this job opportunity! "
        "Please find my attached resume for your consideration.\n\n"
        "Best regards,\nRahul Tomer"
    )
    message.attach(MIMEText(body_text, "plain"))

    # Attach PDF Resume
    if os.path.exists(RESUME_PATH):
        with open(RESUME_PATH, "rb") as f:
            pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
            pdf_attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(RESUME_PATH),
            )
            message.attach(pdf_attachment)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    body = {"raw": raw_message, "threadId": thread_id}

    try:
        sent_message = service.users().messages().send(userId="me", body=body).execute()
        
        print(f"✅ Success: Resume sent to {to_email} | Message ID: {sent_message['id']}")
        
        with open("activity_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] SENT RESUME TO: {to_email} | Subject: {original_subject} | Message ID: {sent_message['id']}\n")

    except Exception as e:
        print(f"❌ Failed to send resume to {to_email}: {e}")


def process_unread_emails(service):
    """Fetches and handles unread inbox emails."""
    results = (
        service.users()
        .messages()
        .list(userId="me", q="is:unread in:inbox")
        .execute()
    )
    messages = results.get("messages", [])

    if not messages:
        print("No new unread emails.")
        return

    print(f"Found {len(messages)} unread email(s)...")

    for msg_info in messages:
        msg_id = msg_info["id"]
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

        thread_id = msg.get("threadId")
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        sender = next(
            (h["value"] for h in headers if h["name"].lower() == "from"),
            "Unknown",
        )
        subject = next(
            (h["value"] for h in headers if h["name"].lower() == "subject"),
            "No Subject",
        )

        body = msg.get("snippet", "")

        print(f"\nProcessing Email: '{subject}' from {sender}")

        category = classify_email(sender, subject, body)
        print(f"   -> AI Classification: {category}")

        if category == "PROMOTIONAL":
            service.users().messages().trash(userId="me", id=msg_id).execute()
            print("  Action: Email moved to TRASH.")
            with open("activity_log.txt", "a", encoding="utf-8") as f:
                f.write(f"[{time.ctime()}] 🗑️ TRASHED (Spam/Promo): {subject} | From: {sender}\n")

        elif category == "JOB_OPPORTUNITY":
            send_auto_reply(service, thread_id, sender, subject)
            service.users().messages().batchModify(
                userId="me",
                body={"ids": [msg_id], "removeLabelIds": ["UNREAD"]},
            ).execute()
            print("  Action: Resume sent & marked as read.")

        else:  # OTHER
            service.users().messages().batchModify(
                userId="me",
                body={"ids": [msg_id], "removeLabelIds": ["UNREAD"]},
            ).execute()
            print("  Action: Marked as read.")
            with open("activity_log.txt", "a", encoding="utf-8") as f:
                f.write(f"[{time.ctime()}] 📖 MARKED READ (Other): {subject} | From: {sender}\n")


def main():
    service = get_gmail_service()
    if not service:
        print("Gmail authentication failed. Exiting...")
        return

    print("Email Automator Active. Listening for incoming messages every 30 seconds...")

    while True:
        try:
            process_unread_emails(service)
        except Exception as e:
            print(f"An error occurred during polling: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()