"""SMS / WhatsApp alerts through Twilio (optional). Always records an outbox row."""
import os
import requests
import db

SID, TOKEN = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
FROM = os.getenv("TWILIO_FROM")                       # e.g. +14155550100
CHANNEL = os.getenv("NOTIFY_CHANNEL", "sms")          # sms | whatsapp


def send(field, text):
    phone = (field.get("contact_phone") or "").strip()
    if not phone:
        return "skipped"
    status = "logged"                                 # no provider configured: outbox only
    if SID and TOKEN and FROM:
        pre = "whatsapp:" if CHANNEL == "whatsapp" else ""
        try:
            r = requests.post("https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % SID, timeout=8,
                              auth=(SID, TOKEN), data={"To": pre + phone, "From": pre + FROM, "Body": text})
            status = "sent" if r.status_code < 300 else "failed"
        except requests.RequestException:
            status = "failed"
    db.execute("INSERT INTO notifications (field_id, phone, channel, message, status) VALUES (%s,%s,%s,%s,%s)",
               (field["id"], phone, CHANNEL, text[:500], status))
    print("[notify]", status, phone, text)
    return status
