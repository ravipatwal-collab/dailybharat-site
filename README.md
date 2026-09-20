# www.dailybharat10.com

Static site for the Daily Bharat News YouTube channel (@dailybharat10), served by GitHub Pages.

- Every public YouTube playlist becomes a Topic page under `/topics/` automatically (new Finance, Lifestyle, etc. playlists appear on the next build).
- `build.py` reads the channel's public YouTube RSS feed, keeps every video seen in `data/videos.json`,
  and generates `index.html`, `news/<id>/`, `archive/`, `privacy-policy.html`, `terms.html`, `sitemap.xml`, `robots.txt`.
- `.github/workflows/update.yml` re-runs it every 2 hours and commits only when something changed.
- Edit the design in `assets/style.css`, page copy in `build.py`, legal text in `content/`.
- Local preview: `python build.py && python -m http.server 8000`.

Generated files (`index.html`, `news/`, `archive/`, `sitemap.xml`, ...) are committed on purpose: GitHub Pages serves them as-is.
