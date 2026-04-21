"""
Kør dette script ÉN gang lokalt for at få dit Google refresh token.
Derefter gemmer du tokenet som en GitHub Secret.

Krav: pip install requests
Kør: python scripts/get_google_token.py
"""

import webbrowser
import urllib.parse
import requests

print("=" * 60)
print("  Google Calendar — Hent Refresh Token")
print("=" * 60)
print()
print("Du skal bruge OAuth 2.0 credentials fra Google Cloud Console.")
print("Gå til: https://console.cloud.google.com/apis/credentials")
print("Opret et 'OAuth 2.0 Client ID' af typen 'Desktop app'.")
print()

CLIENT_ID     = input("Indtast Client ID:     ").strip()
CLIENT_SECRET = input("Indtast Client Secret: ").strip()

REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
SCOPE        = 'https://www.googleapis.com/auth/calendar.events'

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
print("(Hvis browseren ikke åbner, kopier dette link manuelt:)")
print(auth_url)
print()

code = input("Indsæt den viste autorisationskode her: ").strip()

response = requests.post('https://oauth2.googleapis.com/token', data={
    'code':          code,
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
    print("Tilføj secrets på: https://github.com/DIT-REPO/settings/secrets/actions")
else:
    print()
    print("❌ Fejl:", tokens)
