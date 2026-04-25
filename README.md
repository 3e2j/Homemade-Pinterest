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
- Images are converted to WebP to save space.
- Data (tweets + media) updates only when you click the Refresh button. It is recommended to use this feature sparingly to avoid Twitter/X rate limitations.

## Setup

### 1. Configure Credentials
Create a `.env` file in the project root with your Twitter/X credentials:

```env
USER_ID=your_user_id_here
HEADER_AUTHORIZATION=Bearer your_authorization_token
HEADER_COOKIES=your_complete_cookie_string
HEADER_CSRF=your_csrf_token
```

**How to obtain credentials:**
1. Open Twitter / X in a desktop browser and go to your Likes page.
2. Open DevTools (F12), Network tab.
3. Filter for requests containing `/Likes`.
4. Select a request to `https://x.com/i/api/.../Likes`.
5. Copy the following headers:
   - `authorization` → `HEADER_AUTHORIZATION`
   - `x-csrf-token` → `HEADER_CSRF`
   - full `cookie` string → `HEADER_COOKIES`
6. Find your numeric `userId` in the request payload or URL → `USER_ID`
7. Paste values into the `.env` file.

**Important:** Never share or commit `.env`.

### 2. Configure Application Settings
Edit `config.json`:

```json
{
    "DOWNLOAD_IMAGES": true
}
```

- `DOWNLOAD_IMAGES` (boolean): Whether to download and cache images locally. Set to `true` to reduce repeated remote fetches and rate-limit risk.

### 3. Run

```bash
./start.sh
```

`start.sh` creates a virtual environment, installs dependencies, and starts the server. The app will be available at `http://localhost:8000`.

Click Refresh to fetch new likes and (optionally) download new media.
