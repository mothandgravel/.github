# Moth & Gravel website

This repository contains the [Moth & Gravel](https://mothandgravel.com/) website and the public GitHub organization profile.

## Site structure

- `docs/index.html` — landing-page content and metadata
- `docs/notes/` — published Field Notes and independent studio writing
- `docs/assets/site.css` — colors, layout and responsive styles
- `docs/assets/site.js` — mobile navigation and appearance controls
- `docs/assets/` — brand illustrations, icons and a 1200 × 630 social-preview PNG
- `docs/404.html` — custom not-found page
- `docs/robots.txt` and `docs/sitemap.xml` — search indexing
- `profile/README.md` — GitHub organization overview

The site is statically served through GitHub Pages. There is no server-side application, database, analytics integration or contact form.

## Local preview

```sh
python3 -m http.server 8000 --directory docs
```

Open `http://127.0.0.1:8000/`.

## Quality checks

```sh
python3 scripts/check_site.py
node --check docs/assets/site.js
```

Pull requests also run a browser-based design audit covering the Workbench, Field Notes, appearance modes, social-image metadata, navigation and accessibility. See `DESIGN-REVIEW-01.md` and `DESIGN-REVIEW-02.md` for the design decisions and measured results.

## Publishing

Approved changes to the website are published through the existing GitHub Pages configuration. Hosting, registrar credentials, DNS management and certificate operations are administered outside the public source repository.

Do not commit credentials, registrar records, internal deployment information or private product details.
