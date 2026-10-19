# Point Market website — handoff (updated 2026-10-13)

Read this first in any new session. Owner: Hala (replies in Arabic, Levantine/Gulf mix, concise). No emoji in published content.

## What this is
- Static site at **https://pointmarkets.sa** (live since 2026-10-06), replacing the old WordPress front end. Preview with drafts: https://test.pointmarkets.sa (noindex).
- Repo: **github.com/point-markets/point-website** (public). Moved from aurahani77 on 2026-10-11; GitHub redirects the old URL. Org owner: Hala (aurahani77). Yusef (yusefbaz4) has write access (outside collaborator).
- Pushing needs a fine-grained GitHub token from Hala (resource owner = point-markets, Contents + Workflows read/write). Use it only at push time via `git -c http.extraHeader="Authorization: Basic <base64 x-access-token:TOKEN>"`. Never write it into a file.
- Hosting: cPanel at Sahari (صحاري); nameservers NS11/12/13.SHOOUBADVANCE.COM. Had a full server outage on 2026-10-11 ~17:15 (web + DNS down for everyone); came back on its own. Not caused by site code.

## How it works
- `content/posts/*.md`: YAML front matter (title, slug, status draft|published, date, modified, category `نصائح وأدلة تسوق` | `أخبار بوينت`, description, cover, cover_alt, focus_keyword) + HTML body (house style: «باختصار» box, question H2s, table, Jahez banner, 5-question FAQ, closing link to /branches/).
- `tools/build.py` builds `public/` (published only) and `preview/` (everything, noindex): blog index + categories, articles, /branches/, /privacy-policy/, /terms/, sitemap, llms.txt, posts.json, .htaccess (301s from old WP URLs), cache-busting.
  - Scheduled publishing: `status: published` + future `date` (Riyadh time) stays a draft until that date.
  - `unlink_missing()`: links to posts not in the build become plain text (no broken links on live).
- `tools/theme.py` header/footer; `tools/legal.py` privacy/terms text (company: شركة الفا الغرب التجارية, unified national number 7023567725).
- `static/` homepage (minified React bundle in `static/assets/app.js`; branch data `gt=[...]` lives there), CSS, motion.js, newsletter.js, `htaccess.tpl` (passes Authorization header to WP; WP admin + REST stay working behind the static site).
- `.github/workflows/build.yml`: on push (content/static/tools) + daily cron 06:05 UTC → build, commit public/preview, then `tools/wp_sync.py` mirrors posts into WordPress (published → private, draft → draft, deleted drafts → trash). Secrets: WP_USER, WP_APP_PASSWORD (app password of WP user "Yusef Baz").
  - NOTE: the daily cron did not fire on 2026-10-12 (likely because of the repo transfer). Oct 12 post was released by a manual build+push. Verify the schedule runs; if not, re-save the workflow or trigger it manually.
- cPanel cron every 5 min: `PREVIEW_DIR=$HOME/public_html/test.pointmarkets.sa LIVE_DIR=$HOME/public_html /bin/bash $HOME/repositories/point-website/deploy/deploy.sh >> $HOME/point-deploy.log 2>&1`. Deployed commit visible at /version.txt. No cPanel Terminal available. Hala may have run a temporary every-minute cron to `git remote set-url` to the org URL — make sure it was deleted.
- n8n: subscription ending. "Sync Posts to WordPress" workflow unpublished (replaced by wp_sync.py). Newsletter signup still goes to n8n webhook https://aurash77.app.n8n.cloud/webhook/point-newsletter → data table "Point Newsletter Subscribers"; plan is to move it to Brevo (free) and export subscribers.
- Images live on https://pointmarkets.sa/wp-content/uploads/ or `static/assets/img/`. Never delete wp-content.

## Content status (2026-10-13)
- Published: 15 posts, incl. high-protein-grocery-list (Oct 11, own cover .webp) and weekend-family-breakfast-ideas (Oct 12).
- Drafts awaiting Hala's approval (Oct batch, SEO/GEO, review sheet point-articles-oct-2026.xlsx; White Friday article deleted at her request):
  riyadh-season-2026-outing-snacks, winter-soups-shopping-list, high-fiber-foods-list, matcha-trending-drinks-at-home, healthy-kids-snacks-after-school, saudi-dates-varieties-guide, cheese-types-guide-supermarket, weekly-meal-prep-on-budget.
  All still use placeholder cover `/assets/img/hero.jpg`. Cover prompts: point-article-cover-prompts.xlsx. Hala is making images (her shared Drive folder from layan isn't readable by the connector — ask her to upload files/zip).
- Plan once approved: add covers, set status published with dates one per day, push.

## Open items for Hala
- Approve the 8 drafts + provide covers.
- Brevo account for the newsletter.
- Optional: make Yusef Admin / org Owner; delete old GitHub token.
- Branches «التواصل» and «التحلية» confirmed in Riyadh (listed under وسط; region not specified).

## Working rules
- Screenshot-verify before pushing UI changes (desktop + 390px). Changes show within 5–10 min; tell Hala Ctrl+Shift+R if she sees no change.
- Keep `letter-spacing:0` (Arabic must stay joined). No emoji, no «ميني ماركت», no competitor names in content.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Automation notes (2026-10-19)
- PRs from `claude/*` branches are squash-merged automatically by `.github/workflows/auto-merge-claude.yml`, which then triggers the build. Add the label `hold` to a PR to review it first.
- Scheduled posts are released by a cPanel cron (09:05 server time = Riyadh) that runs `deploy/deploy.sh` with `FORCE=1 BUILD=1`; GitHub's own cron (09:07 / 12:07 Riyadh) is only a backup because GitHub delays or skips scheduled runs.
