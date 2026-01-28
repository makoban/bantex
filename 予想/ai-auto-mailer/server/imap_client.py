#!/usr/bin/env python3
"""
IMAP client for fetching emails
"""
import sys
import json
from datetime import datetime, timezone, timedelta
from imap_tools import MailBox, AND
from email.utils import parseaddr

def fetch_new_emails(imap_host: str, imap_port: int, username: str, password: str, last_checked_timestamp: int = None):
    """
    Fetch new emails from IMAP server
    
    Args:
        imap_host: IMAP server hostname
        imap_port: IMAP server port
        username: IMAP username
        password: IMAP password
        last_checked_timestamp: Unix timestamp (milliseconds) of last check
    
    Returns:
        List of email dictionaries
    """
    try:
        emails = []
        
        # Debug: print to stderr so it shows in logs
        print(f"[Python IMAP] Connecting to {imap_host}:{imap_port} as {username}", file=sys.stderr)
        print(f"[Python IMAP] last_checked_timestamp: {last_checked_timestamp}", file=sys.stderr)
        
        with MailBox(imap_host, imap_port).login(username, password) as mailbox:
            # Build search criteria based on whether this is first check or not
            if last_checked_timestamp is None or last_checked_timestamp == 0:
                # First check: get emails from last 30 days
                thirty_days_ago = datetime.now() - timedelta(days=30)
                criteria = AND(date_gte=thirty_days_ago.date())
                print(f"[Python IMAP] First check mode: fetching since {thirty_days_ago.date()}", file=sys.stderr)
            else:
                # Subsequent checks: get emails since last check date
                # Convert milliseconds to datetime
                last_check_date = datetime.fromtimestamp(last_checked_timestamp / 1000, tz=timezone.utc)
                # Use date_gte to get emails from that date onwards
                criteria = AND(date_gte=last_check_date.date())
                print(f"[Python IMAP] Subsequent check mode: fetching since {last_check_date.date()}", file=sys.stderr)
            
            # Count total messages first
            all_messages = list(mailbox.fetch(criteria, mark_seen=False))
            print(f"[Python IMAP] Found {len(all_messages)} messages matching criteria", file=sys.stderr)
            
            # Fetch ALL messages (regardless of seen/unseen status), don't mark as seen
            for msg in all_messages:
                # Parse sender email
                sender_name, sender_email = parseaddr(msg.from_)
                
                # Get message ID
                message_id = msg.uid or msg.headers.get('message-id', [''])[0]
                
                # Get received date
                received_at = msg.date
                if received_at:
                    # Convert to Unix timestamp (milliseconds)
                    received_timestamp = int(received_at.timestamp() * 1000)
                else:
                    received_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                
                # For subsequent checks, skip emails that were already processed
                # (received before the last check timestamp)
                if last_checked_timestamp and last_checked_timestamp > 0:
                    if received_timestamp <= last_checked_timestamp:
                        print(f"[Python IMAP] Skipping email {message_id} (received {received_timestamp} <= {last_checked_timestamp})", file=sys.stderr)
                        continue
                
                # Extract text content
                text_content = msg.text or msg.html or ""
                
                email_data = {
                    "message_id": str(message_id),
                    "sender": sender_email or msg.from_,
                    "sender_name": sender_name or "",
                    "subject": msg.subject or "(No Subject)",
                    "body": text_content[:5000],  # Limit body length
                    "received_at": received_timestamp,
                }
                
                emails.append(email_data)
                print(f"[Python IMAP] Added email: {msg.subject[:50] if msg.subject else '(No Subject)'}", file=sys.stderr)
        
        print(f"[Python IMAP] Returning {len(emails)} emails", file=sys.stderr)
        
        return {
            "success": True,
            "emails": emails,
            "count": len(emails)
        }
    
    except Exception as e:
        print(f"[Python IMAP] Error: {str(e)}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "emails": [],
            "count": 0
        }

if __name__ == "__main__":
    # Read arguments from command line
    if len(sys.argv) < 5:
        print(json.dumps({
            "success": False,
            "error": "Missing arguments. Usage: imap_client.py <host> <port> <username> <password> [last_checked_timestamp]"
        }))
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2])
    username = sys.argv[3]
    password = sys.argv[4]
    last_checked = int(sys.argv[5]) if len(sys.argv) > 5 else None
    
    print(f"[Python IMAP] Args: host={host}, port={port}, username={username}, last_checked={last_checked}", file=sys.stderr)
    
    result = fetch_new_emails(host, port, username, password, last_checked)
    print(json.dumps(result))
