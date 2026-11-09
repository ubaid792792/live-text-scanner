# LiveText Scanner PWA

A fully client-side Progressive Web Application that runs in a mobile browser and performs real-time OCR (Optical Character Recognition) using Tesseract.js. No server or internet required after initial load.

## Features

- **Live camera preview** — rear camera by default, toggle to front
- **Real-time OCR** — Tesseract.js runs entirely in the browser, processes every 2 seconds
- **Bounding box highlights** — semi-transparent blue rectangles with borders around detected text
- **Selectable scan area** — draw a rectangle on screen to restrict OCR to a specific region
- **Copy text** — one-tap copy of all detected text to clipboard with flash animation
- **Fullscreen mobile UI** — minimal chrome, gesture-friendly controls
- **Fully offline capable** — after initial load, all processing is client-side

## File Structure

```
LiveTextScanner-PWA/
├── index.html          # Single-file complete application
└── README.md           # This file
```

Everything is self-contained in `index.html` (embedded CSS + JS).

## How to Use

### Open the App

| Method | Instructions |
|--------|-------------|
| **Serve locally** | `python3 -m http.server 8080` then visit `http://localhost:8080` |
| **Deploy static host** | Upload `index.html` to Netlify, Vercel, GitHub Pages, etc. |
| **Open directly** | `file://` protocol does not work with `getUserMedia`. Must use HTTP/HTTPS. |

### Controls

| Control | Location | Action |
|---------|----------|--------|
| 🔄 Camera flip | Top-right | Switch between front/rear camera |
| ⬜ Scan area | Top-left | Enter scan area selection mode |
| ✕ Clear scan | Below scan button | Remove the selected scan area |
| COPY TEXT | Bottom-center | Copy all detected text to clipboard |

### Scan Area Feature

1. Tap the **⬜** button to enter scan mode (screen dims slightly)
2. **Drag** on the screen to draw a rectangle
3. Only text **inside** the rectangle will be detected and highlighted
4. Tap the **✕** button to clear the selection
5. Tap **⬜** again to exit scan mode

The scan area persists across camera switches and frame updates.

## Technical Architecture

```
Camera (getUserMedia)
    │
    ├─► <video> element (preview)
    │
    └─► Offscreen canvas (640px wide, cropped to match display AR)
            │
            ▼
        Tesseract.js OCR
            │
            ▼
        [{word, bbox, confidence}, ...]
            │
            ▼
        Filter by scan area (if active)
            │
            ▼
        Draw overlay canvas (highlights)
        Update "COPY TEXT" button
        Show/hide "No text detected"
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **640px processing width** | Balances OCR accuracy vs performance on mobile |
| **2-second interval** | Avoids battery drain; Tesseract takes ~1-2s per frame on mobile |
| **Object-fit: cover** | Standard camera app behavior; crop to fill screen |
| **Cropped capture** | Coordinates from OCR map directly to display coordinates |
| **Single HTML file** | Zero build step, deploy anywhere with one file |
| **Touch + mouse handlers** | Works on mobile (touch) and desktop (mouse) |

## Dependencies

| Library | Version | Purpose | Loaded From |
|---------|---------|---------|-------------|
| Tesseract.js | v5 | Client-side OCR engine | `cdn.jsdelivr.net/npm/tesseract.js@5` |

No other external dependencies. Tesseract.js downloads language data (~2MB for English) on first use and caches it in IndexedDB.

## Testing

### On a Real Device (Recommended)

1. **Host the file** on a local server or deploy to a public URL
   ```bash
   cd LiveTextScanner-PWA
   python3 -m http.server 8080
   ```
2. **Find your local IP** (e.g., `192.168.1.100`)
3. **Open on phone** at `http://192.168.1.100:8080`
4. Both devices must be on the same WiFi network

### Using Chrome DevTools (Desktop)

1. Open `index.html` via `python3 -m http.server 8080`
2. Open Chrome DevTools → Toggle Device Toolbar (Ctrl+Shift+M)
3. Select a mobile device (e.g., Pixel 7) from the device toolbar
4. Camera will use your laptop's webcam (front-facing)
5. Test OCR by pointing your webcam at printed text

### Known Limitations

| Issue | Cause | Workaround |
|-------|-------|------------|
| **First frame slow** | Tesseract.js downloads language data | Wait 5-10s after page load |
| **Low accuracy on stylized fonts** | Tesseract is trained on printed text | Use clear, standard fonts |
| **No text detected in dim light** | Camera exposure too low | Ensure adequate lighting |
| **Small text not recognized** | Resolution limit at 640px processing | Move camera closer to text |
| **iOS Safari: fullscreen** | Some iOS versions restrict fullscreen API | Home screen add-to-bookmark works |
| **Rear camera unavailable on desktop** | Most laptops only have front camera | Use Android/iOS device for testing |

## Deployment Guide

### Option 1: Static Host (Recommended)

Upload `index.html` to any static host:

- **Netlify**: Drag `index.html` to `netlify.com/drop`
- **Vercel**: `vercel deploy --prod index.html`
- **GitHub Pages**: Push to a repo, enable Pages
- **Surge**: `surge . livetext-scanner.surge.sh`

All URLs must be served over **HTTPS** for `getUserMedia` to work.

### Option 2: Docker

```dockerfile
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
```

### Option 3: Install as PWA (Manual)

1. Open the app in Chrome on Android
2. Tap the "Install" prompt or menu → "Add to Home Screen"
3. The app opens in fullscreen without browser chrome

## Performance Optimization

| Suggestion | Impact |
|------------|--------|
| Use English-only (`'eng'` parameter in `createWorker`) | Faster initialization, smaller download |
| Reduce `PROCESS_W` to 480 | Faster OCR, lower accuracy |
| Increase interval to 3000ms | Better battery life |
| Use `object-fit: fill` instead of `cover` | Simpler coordinate math, stretched preview |
| Pre-download language data with Tesseract.js | No delay on first frame |

## Browser Compatibility

| Browser | Camera | Tesseract.js | Fullscreen | Notes |
|---------|--------|-------------|------------|-------|
| Chrome Android | ✅ | ✅ | ✅ | Best experience |
| Safari iOS 15+ | ✅ | ✅ | Partial | Add to Home Screen for fullscreen |
| Firefox Android | ✅ | ✅ | ✅ | Good |
| Samsung Internet | ✅ | ✅ | ✅ | Good |
| Chrome Desktop | ✅ | ✅ | N/A | Uses webcam |
| Safari Desktop | ❌ | ✅ | N/A | No `getUserMedia` for `environment` |

## License

MIT
