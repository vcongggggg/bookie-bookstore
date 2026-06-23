# Portfolio Media Checklist

Last updated: 2026-06-23

This file tracks real media used by `index.html`. The page still works without
external hosting or JavaScript-heavy media. Current media files live in:

```text
portfolio/media/
```

## Completed

### 1. Bookie checkout proof

Status: done with real Playwright-recorded video plus screenshot fallback.

Files added:

- `media/bookie-checkout-demo.webm`
- `media/bookie-checkout.png`
- `media/bookie-payment.png`
- `media/bookie-order.png`

Where used:

- `work-section`
- Featured Bookie Bookstore card
- `.work-visual.visual-wide`

Current behavior:

- The old CSS-only `.bookie-board` and `.bookie-phone` mockup has been replaced
  by a real autoplaying, muted WebM checkout demo.
- The section also keeps screenshot proof for simulated payment confirmation
  and order detail.

Future optional upgrade:

- Re-record a tighter 4-6 second edit if you want a shorter hero proof clip.
- Convert WebM to MP4 later only if a target hosting platform requires MP4.

### 2. Window-section timeline thumbnails

Status: done with real Bookie proof thumbnails.

Files used:

- `media/bookie-checkout.png`
- `media/bookie-dashboard.png`
- `media/bookie-chatbot.png`

Where used:

- `portfolio-window-section`
- `.window-cards`

Current behavior:

- The three timeline cards now include real screenshots instead of text-only
  cards.

Future optional upgrade:

- Replace `media/bookie-dashboard.png` with a GitHub Actions green-run
  screenshot after the public workflow runs on GitHub.

### 3. User intelligence proof

Status: done with real profile, Reading DNA, and reading history screenshots.

Files added:

- `media/bookie-profile.png`
- `media/bookie-reading-dna.png`
- `media/bookie-reading-history.png`

Where used:

- `user-intel-section`
- `.intel-media-grid`

Current behavior:

- The portfolio now shows the personalization side of Bookie: account profile,
  Reading DNA analytics, reading history, preference charts, recommendations,
  and behavior signals.

Follow-up completed:

- `media/bookie-features/24-customer-book-sentiment-analysis.png` now captures
  the AI sentiment summary after fixing the missing sentiment word-list bug.

### 4. Full Bookie feature screenshot archive

Status: done with 46 desktop screenshots covering public pages, auth, customer
account, commerce, reader, chatbot, API/health, admin dashboard, RBAC, inventory,
coupons, orders, audit log, and Django admin.

Folder added:

- `media/bookie-features/`

Index:

- `media/bookie-features/README.md`

Current behavior:

- The archive gives a complete local evidence set for portfolio editing and CV
  proof without relying on manual browser screenshots.

Known gap:

- Invoice PDF is not included as a PNG because the route downloads a PDF in
  headless Chromium instead of rendering an HTML preview.

## Still Optional

### 5. Smart Parking OCR real media

Status: optional, waiting for real hardware/dashboard media.

Current behavior:

- The portfolio keeps the SVG flow diagram because no local hardware photo or
  dashboard media was found.

Best future media:

- ESP32 + RFID + camera rig photo.
- Or dashboard screenshot showing a real plate/session.

### 6. Smart Greenhouse real media

Status: optional, waiting for real hardware/dashboard media.

Current behavior:

- The portfolio keeps the SVG flow diagram because no local greenhouse photo or
  Socket.IO dashboard media was found.

Best future media:

- Greenhouse rig photo.
- Or short GIF/video of sensor values updating live.

## Notes

- Keep media small; target under 3-4MB per video/GIF.
- Prefer MP4/WebM for animation because it is smaller than GIF.
- Keep visual grading close to the black/white portfolio style.
- Use descriptive `alt` text for every image.
