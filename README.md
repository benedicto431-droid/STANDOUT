# STANDOUT B&C

A responsive website for the Nairobi construction company, with a Cohere-powered AI assistant, a private management inbox, a publishing CMS, and moderated visitor reviews and comments.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open the preview at the root URL. The administrator sign-in is at `/admin/login`.

For a local first run, the requested starter credentials are:

- Username: `admin`
- Password: `admin123`

Change these before exposing the site to the public. The app reads `ADMIN_USERNAME` and `ADMIN_PASSWORD` from the environment; Render refuses to start with the default password.

## Content, reviews and comments

- Sign in at `/admin/login`, then use **Content** to create drafts or publish blog posts, articles, news, project updates, and other text content.
- Published entries appear in the public journal at `/journal` and can receive moderated comments.
- Visitors can submit a review or general comment at `/community`. Submissions are private until approved in **Reviews & comments** in the admin workspace.
- Optional cover images use an `http://` or `https://` image URL. The web service does not save uploaded image files to its local filesystem.

## Cohere AI

The Cohere key is only read by the Flask server. Do not put it in HTML, JavaScript, source control, or a browser request.

- In Replit, save it as the `COHERE_API_KEY` secret to enable Cohere in the preview.
- In Render, add `COHERE_API_KEY` under the web service's Environment settings. The included `render.yaml` prompts for it as a private value.
- The default model is `command-a-03-2025`. To change it, set `COHERE_MODEL`.

Without a Cohere key the chat uses a small company-information fallback so the preview stays usable. Once a key is configured, messages are answered by Cohere's Chat API.

## Deploy on Render

1. Push this project to a GitHub repository.
2. In Render, create a Web Service from that repository and choose the included Blueprint configuration (`render.yaml`).
3. Create a Render PostgreSQL database and set the web service's `DATABASE_URL` to that database's **internal connection URL**. Keep it on the same region as the web service.
4. Set a strong private `ADMIN_PASSWORD`. The username defaults to `admin`; you can change it with `ADMIN_USERNAME`.
5. Add your Cohere API key as `COHERE_API_KEY` in Render's Environment settings.
6. Deploy. The service binds to Render's `PORT`, builds with `pip install -r requirements.txt`, and uses `/health` for its health check.

The Blueprint prompts for `DATABASE_URL`, `ADMIN_PASSWORD`, and `COHERE_API_KEY`. Do not leave `DATABASE_URL` unset for a live site: the local SQLite database is stored on the web service filesystem, which is temporary on Render. The database tables for the inbox, published content, and visitor submissions are created when the app starts; use the same PostgreSQL database for subsequent deploys to retain that data.

## Company details

STANDOUT B&C provides new and custom home construction, commercial and light industrial work, renovations, additions, kitchen and bathroom remodels, foundations, roofing, framing, project management, and design-build services.

Office: Park Plaza Building, along Eastern Bypass, Utawala, Nairobi  
Phone: 0731157929  
Director: CPM. Okolla Felix  
Site Engineer: B.Tech Frank Okotsi

Project photos have not been supplied yet; the site leaves the gallery ready for the company's real work rather than showing invented projects.
