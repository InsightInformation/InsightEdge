# Your Backup Plan

Launch kit for **Your Backup Plan**, Ashley Harris's flexible helping-hand service for businesses, organizations, schools and busy individuals in the South Hills of Pittsburgh and Washington County.

> *Extra help. Real solutions. When you need help, but don't need another employee.*

## What's here

| Folder | What it is |
|---|---|
| `website/` | A complete one-page website that works on phones and computers, matching the flyer's look. Open `website/index.html` in a browser to preview it |
| `marketing/launch-posts.md` | Ready-to-paste copy for Facebook, Google Business Profile, Nextdoor, local groups, Instagram and LinkedIn, plus ongoing post ideas |
| `marketing/outreach-scripts.md` | Emails, walk-in script, follow-ups, review requests, and how to answer "what do you charge?" |
| `marketing/first-90-days.md` | Week-by-week launch plan and business card text |
| `business/pricing.md` | Recommended rates, the market math behind them, and what she actually takes home |
| `business/launch-checklist.md` | Pennsylvania setup: LLC, EIN, taxes, insurance, clearances, and a startup budget |
| `business/service-agreement.md` | One-page client agreement and a new-client intake checklist |

## Put the website online (free)

The site is plain HTML/CSS/JS, so no build step and no monthly hosting fee.

**Easiest: Netlify Drop**
1. Go to https://app.netlify.com/drop and create a free account.
2. Drag the `website` folder (or `your-backup-plan-website.zip`) onto the page. It's live in seconds at a `*.netlify.app` address.
3. To use a custom domain (for example `yourbackupplanpgh.com`, about $12–20/yr), buy it at Cloudflare, Porkbun or Namecheap, then add it under **Domain settings** in Netlify.

Other free options: Cloudflare Pages or GitHub Pages.

**After it's live**
- In `website/index.html`, change `assets/flyer.jpg` in the `og:image` tag to the full URL (for example `https://yourbackupplanpgh.com/assets/flyer.jpg`) so the flyer shows when the link is shared on Facebook or by text.
- Add the website link to the Facebook page, Google Business Profile, email signature and business cards.

## Contact form

Out of the box, the form opens the visitor's email app with their request pre-filled and addressed to `yourbackupplan.ashley@gmail.com`. To receive requests directly (so visitors don't need an email app):

1. Create a free form at https://formspree.io using Ashley's email.
2. Copy the form URL (looks like `https://formspree.io/f/abcdwxyz`).
3. Paste it into `FORM_ENDPOINT` at the top of the contact-form section in `website/script.js`.

## Things for Ashley to confirm before launch

- [ ] Every service, bio and FAQ answer on the site sounds like her and is accurate
- [ ] School clearances are current (the FAQ says she can provide them)
- [ ] The Facebook page `@YourBackupPlan` exists at that address
- [ ] Final rates (the site intentionally doesn't list prices, so she can quote per job)
- [ ] The service-area town list in the FAQ
