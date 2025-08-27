# Homemade Pinterest

A self-hosted, Pinterest-like web app for viewing Twitter/X media locally.
The app obtains your liked tweets, and allows you to browse them in a grid-view.

You can choose to download all images, caching them locally - or receive them directly from Twitter/X's API.

<!-- TODO ![example output rendered html of image grid](example_html_output.png) -->

## Features

- **Pinterest-style grid layout** for much easier browsing of your Twitter/X Likes.
- **Automatic media download:** Saves tweet images and user avatars for offline access.
- **Privacy blur:** For detected sensitive media.

## Important Information
- Never share your credentials with anyone. Your credentials are only used to authenticate with Twitter, and are never sent elsewhere. 

- It is recommended to leave the `DOWNLOAD_IMAGES` flag to true to avoid rate-limit restrictions by Twitter/X.

- All downloaded images are converted to webp format to reduce disk space usage.

- After a first run, the app will not update any data until the "Refresh" button is clicked. It is recommended to use this feature sparingly to avoid Twitter/X rate limitations.

## Setup

### 1. Install Requirements

This project requires Python 3.7+ and the `requests` library.

```bash
pip install -r requirements.txt
```

### 2. Configure Access

To import images from your Twitter likes, you need to provide credentials so the script can access your account data. Modify `config.json` and fill in the required fields:

- `HEADER_AUTHORIZATION`
- `HEADER_COOKIES`
- `HEADER_CSRF`
- `USER_ID`
- `DOWNLOAD_IMAGES` (default set to `true`)

**How to get your Twitter/X credentials:**

1. Open your browser and go to your Twitter Likes page.
2. Open Developer Tools (`F12` or `Ctrl+Shift+I`), go to the Network tab.
3. Find a request to `x.com/i/api/...` ending in `/Likes`.
4. Copy the `Authorization`, `Cookies`, and `x-csrf-token` values from the request headers.

    Note that while pasting cookie value, you would need to escape any existing double quotes by prefixing them with a backslash `\`

5. Find your numeric Twitter `userId` in the request payload or URL.
6. Paste these values into your `config.json`.

### 3. Run the program

Run `start.sh` or `gallery_server.py` and a tab should open at `http://localhost:8000/index.html`

It will automatically start downloading tweet content.