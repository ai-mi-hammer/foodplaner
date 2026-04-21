"""
Kør dette script ÉN gang lokalt for at få dit Google refresh token.
Derefter gemmer du tokenet som en GitHub Secret.

Krav: pip install requests
Kør: python scripts/get_google_token.py

OBS: Bruger localhost-redirect (OOB-flowet er udfaset af Google i 2022).
"""

import http.server
import threading
import urllib.parse
import webbrowser
import requests

print("=" * 60)
print("  Google Calendar — Hent Refresh Token")
print("=" * 60)
print()
print("Du skal bruge OAuth 2.0 credentials fra Google Cloud Console.")
print("Gå til: https://console.cloud.google.com/apis/credentials")
print()
print("Sørg for at din OAuth-client har denne Authorized redirect URI:")
print("  http://localhost:8765/callback")
print("(Credentials → din client → Edit → Authorized redirect URIs)")
print()

CLIENT_ID     = input("Indtast Client ID:     ").strip()
CLIENT_SECRET = input("Indtast Client Secret: ").strip()

REDIRECT_URI = 'http://localhost:8765/callback'
SCOPE        = 'https://www.googleapis.com/auth/calendar.events'

auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        auth_code = params.get('code', [None])[0]
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        if auth_code:
            self.wfile.write(b'<h2>&#x2705; Godkendt! Du kan lukke dette vindue og g&aring; tilbage til terminalen.</h2>')
        else:
            self.wfile.write(b'<h2>&#x274C; Ingen kode modtaget.</h2>')

    def log_message(self, format, *args):
        pass  # Undertrykker server-log

server = http.server.HTTPServer(('localhost', 8765), CallbackHandler)
thread = threading.Thread(target=server.handle_request)
thread.daemon = True
thread.start()

auth_url = (
    'https://accounts.google.com/o/oauth2/auth'
    f'?client_id={urllib.parse.quote(CLIENT_ID)}'
    f'&redirect_uri={urllib.parse.quote(REDIRECT_URI)}'
    f'&scope={urllib.parse.quote(SCOPE)}'
    '&response_type=code'
    '&access_type=offline'
    '&prompt=consent'
)

print()
print("Åbner browser til Google login...")
webbrowser.open(auth_url)
print("Venter på godkendelse i browseren...")
thread.join(timeout=120)
server.server_close()

if not auth_code:
    print("❌ Timeout — ingen kode modtaget inden 120 sekunder.")
    exit(1)

response = requests.post('https://oauth2.googleapis.com/token', data={
    'code':          auth_code,
    'client_id':     CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'redirect_uri':  REDIRECT_URI,
    'grant_type':    'authorization_code',
})

tokens = response.json()

if 'refresh_token' in tokens:
    print()
    print("=" * 60)
    print("  ✅ Succes! Gem disse som GitHub Secrets:")
    print("=" * 60)
    print(f"  GOOGLE_CLIENT_ID:     {CLIENT_ID}")
    print(f"  GOOGLE_CLIENT_SECRET: {CLIENT_SECRET}")
    print(f"  GOOGLE_REFRESH_TOKEN: {tokens['refresh_token']}")
    print("=" * 60)
    print()
    print("Tilføj secrets på: https://github.com/ai-mi-hammer/foodplaner/settings/secrets/actions")
else:
    print()
    print("❌ Fejl:", tokens)
