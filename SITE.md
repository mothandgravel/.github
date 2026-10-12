# Moth & Gravel — GitHub Pages landing site

A single-page, framework-free website for **mothandgravel.com**. Files in `docs/` are the deployable site, while `profile/` remains the GitHub organization profile.

## Publishing

1. Go to **[Repository Settings → Pages](https://github.com/mothandgravel/.github/settings/pages)**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Set branch to `main`, folder to **`/docs`**, and save.
4. Under **Custom domain**, confirm or set **`mothandgravel.com`** and save. The `docs/CNAME` file is already committed to the publishing folder.
5. Finish **GitHub organization domain verification** using the organization-generated TXT challenge. Verification of the domain is separate from Pages custom-domain setup.
6. Only after the site/domain has been configured in GitHub, update DNS at your domain registrar.
7. Once DNS resolves and GitHub provisions TLS, turn on **Enforce HTTPS** in Pages settings.

### Registrar DNS

For apex `mothandgravel.com`, create these four **A** records (name `@`):

| Type | Name | Value |
| --- | --- | --- |
| A | @ | `185.199.108.153` |
| A | @ | `185.199.109.153` |
| A | @ | `185.199.110.153` |
| A | @ | `185.199.111.153` |

For `www.mothandgravel.com` add:

| Type | Name | Value |
| --- | --- | --- |
| CNAME | www | `mothandgravel.github.io` |

Keep existing MX/TXT records for email and domain verification. Remove conflicting parked/default A records where required. Avoid wildcard DNS. IPv6 AAAA records are optional; GitHub documents them at the URL below.

**Official reference:** https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

This repository is an ordinary Pages *project* site. Before custom-domain activation its default URL would be `https://mothandgravel.github.io/.github/`; with the custom domain, the site uses `https://mothandgravel.com/`. For a future dedicated organization Pages repository, `mothandgravel.github.io` can be considered without needing to change the visual identity.

## Architecture

- `docs/index.html` — accessible, semantic landing page, social metadata and all public copy
- `docs/assets/site.css` — design system and responsive layout
- `docs/assets/site.js` — accessible menu and optional afterlight color theme
- `docs/assets/moth-mark.svg` — transparent illustration derived from the organization's vector mark
- `docs/assets/favicon.svg` — standalone icon
- `docs/404.html`, `docs/robots.txt`, `docs/sitemap.xml` — operations and discoverability
- `docs/CNAME` — GitHub Pages custom-domain declaration

No dependencies, bundler, cookies, remote fonts, trackers, third-party scripts, or forms. A localStorage preference is used only for the optional display theme and gracefully degrades when unavailable.

## Local preview

From the repository root:

```bash
python3 -m http.server 8000 --directory docs
```

Open http://localhost:8000/. This is a local preview only; it does not deploy or change DNS.

## Launch verification

- On desktop and mobile, check anchor navigation, responsive menu, and theme switch.
- Confirm the moth illustration and favicon load, and all site links work.
- Check 404, `robots.txt`, and `sitemap.xml`.
- Verify domain DNS, `www` redirect, and HTTPS.
- Do not list private products or claim a public sales/contact channel before one exists.

The source currently lives inside the profile repository as a pragmatic launch choice because the GitHub app connection can write files but does not create repositories or change Pages settings. If the site grows, it can move to a dedicated website repository.
