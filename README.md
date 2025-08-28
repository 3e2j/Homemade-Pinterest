# Homemade Pinterest

A self-hosted, Pinterest-like web app for viewing Twitter/X media locally.
The app obtains your liked tweets, and allows you to browse them in a grid-view.

You can choose to download all images, caching them locally - or receive them directly from Twitter/X's API.

![Homemade Pinterest example](https://imgur.com/1VrhPjn.png)

## Features

- **Pinterest-style grid layout** for much easier browsing of your Twitter/X Likes.
- **Automatic media download:** Saves tweet images and user avatars for offline access.
- **Privacy blur:** For detected sensitive media.

## Important Notes
- Never share your credentials. They are only used to authenticate to Twitter / X.
- Leaving `DOWNLOAD_IMAGES` set to `true` reduces repeated remote fetches and lowers rate‑limit risk.
- Images are converted to WebP to save space.
- Data (tweets + media) updates only when you click the Refresh button. It is recommended to use this feature sparingly to avoid Twitter/X rate limitations

## Setup

### 1. Install Requirements
Python 3.9+ is recommended.
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
Edit `config.json`:

- `USER_ID`
- `HEADER_AUTHORIZATION`
- `HEADER_COOKIES`
- `HEADER_CSRF`
- `DOWNLOAD_IMAGES` (boolean)

How to obtain them:
1. Open Twitter / X in a desktop browser and go to your Likes page.
2. Open DevTools (F12), Network tab.
3. Filter for requests containing `/Likes`.
4. Select a request to `https://x.com/i/api/.../Likes`.
5. Copy headers:
   - `authorization`
   - `x-csrf-token`
   - full `cookie` string
6. Find your numeric `userId` in the request payload or URL.
7. Paste into `config.json`.  
   If your cookie string contains double quotes, escape them with a backslash (`\"`).

### 3. Run
Launch the server:
```bash
python gallery_server.py
```
A browser tab will open at:
```
http://localhost:8000/index.html
```
Click Refresh to fetch new likes and (optionally) download new media.

## Disclaimer
Use responsibly and only for personal archival / viewing of your own liked content.