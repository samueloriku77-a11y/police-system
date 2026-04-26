import asyncore
import smtpd
import sys

print("🚀 Local SMTP Debug Server starting on localhost:1025")
print("📧 Emails received will be printed to console")
print("Stop with Ctrl+C")

class DebugSMTPServer(smtpd.SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data):
        print(f"\n{'='*60}")
        print(f"📨 NEW EMAIL RECEIVED!")
        print(f"From: {mailfrom}")
        print(f"To: {rcpttos}")
        print(f"Peer: {peer}")
        print(f"Subject: (parse from data)")
        print(f"Content Preview:\n{data.decode('utf-8', errors='ignore')[:1000]}...")
        print(f"{'='*60}\n")

try:
    server = DebugSMTPServer(('localhost', 1025), None)
    asyncore.loop()
except KeyboardInterrupt:
    print("\n👋 SMTP server stopped")

