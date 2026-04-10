# HEIC → PNG Converter

A simple desktop app to convert HEIC/HEIF images to PNG — one at a time or in bulk.

## Download

Grab the latest **HEIC to PNG.exe** from the [Releases](../../releases) page — no install or Python needed.

## Usage

- **Single file** — Browse to a `.heic` file and click **Convert**.
- **Bulk folder** — Browse to a folder containing `.heic` files and click **Convert All**.
- **Output folder** — Optionally pick a destination folder. If left blank, PNGs are saved next to the originals.

## Development

```bash
pip install -r requirements.txt
python app.py
```

### Build the executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "HEIC to PNG" app.py
```

The `.exe` will be in the `dist/` folder.
