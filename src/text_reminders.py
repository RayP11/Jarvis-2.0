import smtplib
import os
from dotenv import load_dotenv
import ssl
from email.message import EmailMessage
import imaplib
import email

# Load environment variables
load_dotenv()

email_sender = os.getenv("EMAIL_SENDER")
email_password = os.getenv("EMAIL_PASSWORD")
email_receiver = os.getenv("MY_NUMBER")  # e.g., 4438964231@vzwpix.com
soph_number = os.getenv("SOPHIE_NUMBER")  # another MMS address
dad_number = os.getenv("DAD_NUMBER")

def send_reminder(message):
    """Send a text reminder to yourself."""
    body = message
    em = EmailMessage()
    em['From'] = email_sender
    em['To'] = email_receiver
    em.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.send_message(em)

    print(f"✅ Reminder sent: {message}")

def send_message(message):
    """Send a text message to Sophie."""
    body = message
    em = EmailMessage()
    em['From'] = email_sender
    em['To'] = soph_number
    em.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.send_message(em)

    print(f"✅ Message sent: {message}")

def send_message_with_audio(message, audio_path):
    """Send an audio message to yourself via MMS."""
    body = message
    em = EmailMessage()
    em['From'] = email_sender
    em['To'] = email_receiver  # must be a @vzwpix.com or MMS address
    em.set_content(body)

    with open(audio_path, 'rb') as audio_file:
        audio_data = audio_file.read()
        audio_name = os.path.basename(audio_path)
        subtype = 'mpeg' if audio_name.lower().endswith('.mp3') else 'wav'
        em.add_attachment(audio_data, maintype='audio', subtype=subtype, filename=audio_name)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.send_message(em)

    print(f"✅ Sent: '{message}' with {audio_name} to {soph_number}")

def check_for_sms_replies(phone_email):
    """Poll Gmail for new replies from the specified MMS email address."""
    imap_server = "imap.gmail.com"
    imap_user = email_sender
    imap_pass = email_password  # Use an App Password if 2FA is enabled

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(imap_user, imap_pass)
        mail.select("inbox")

        status, messages = mail.search(None, f'(UNSEEN FROM "{phone_email}")')
        if status != "OK" or not messages[0]:
            return None

        for num in messages[0].split():
            typ, data = mail.fetch(num, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset)
                        break
            else:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

            mail.store(num, '+FLAGS', '\\Seen')  # ✅ Mark as read

            print(f"📩 New SMS reply from {phone_email}: {body.strip()}")
            return body.strip()

        mail.logout()
    except Exception as e:
        print(f"❌ Error checking Gmail: {e}")
        return None

