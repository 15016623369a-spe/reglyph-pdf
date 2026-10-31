# Installation and runtime

## Supported environment

Use 64-bit **Python 3.11** on macOS or Windows x64. Apple Silicon devices including M1/M2-class machines and newer configurations fall within the intended operating range. This is a general desktop application: higher-performance devices use the same installation and document format.

Batch size, page resolution, open text layers, and repair context determine memory and processing requirements. Start with a representative page, then increase the batch size. The default two-thread CPU budget favors controlled resource use; adjust `IPDF_CPU_THREADS=1`, `2`, `3`, or `4` when needed. A thread budget is not a temperature limit or a guarantee of proportional speedup.

## Install from source

```bash
git clone https://github.com/15016623369a-spe/reglyph-pdf.git
cd reglyph-pdf
```

On macOS:

```bash
python3.11 bootstrap.py
./launch.command
```

On Windows, install Python 3.11 x64 with the Python Launcher, then:

```powershell
py -3.11 bootstrap.py
.\launch.bat
```

You can also double-click `install.command` / `install.bat` followed by `launch.command` / `launch.bat`.

The installer creates `.venv-editor` and `.venv-inpaint` inside the source directory and checks their dependency consistency. It keeps the newer OCR stack isolated from IOPaint's NumPy/Pillow requirements. Recreate these environments on another machine instead of copying them between operating systems.

`bootstrap.py --editor-only` installs the editing/OCR environment for workflows using an existing repair endpoint. `--dry-run` asks pip to resolve dependencies without installing them; it still requires access to the package index.

## Models and network

Package installation and the first model download require network access. Downloaded model weights are cached and reused. Standard OCR and repair requests run locally. The editor's OCR configuration allows explicit local detection and recognition model paths.

Set `IPDF_MODEL_DIR` to reuse an existing compatible model cache. Otherwise a bundled `model/` directory is used if present; the fallback is the model folder under the per-user application data directory.

## Start and diagnose

Run the platform launcher, or use the editing environment's interpreter:

```bash
python launcher.py
python launcher.py --check
```

`--check` verifies editor dependencies and the local LaMa endpoint. The service binds to `127.0.0.1:18181`. Logs are stored in the application data folder. If that port belongs to another application, resolve the conflict or configure an existing compatible endpoint in the editor.

A launcher only stops a service process it created; it does not terminate an unrelated process on port 8080 or elsewhere.

## Application data

| Platform | Default data folder |
| --- | --- |
| macOS | `~/Library/Application Support/ReGlyphPDF` |
| Windows | `%LOCALAPPDATA%\ReGlyphPDF` |

Settings, logs, operation records, recovery projects, and bounded repair caches live here. Use `IPDF_DATA_DIR` for an explicit alternate location. User-selected projects and exports are saved at the locations chosen in the editor.

## Troubleshooting

**Python version mismatch:** run the installer with Python 3.11 rather than upgrading every package in an existing environment.

**Old letters remain visible:** editing a text box does not erase text embedded in the background. Enable background clearing during replacement or use a local touch-up.

**Repair endpoint unavailable:** inspect the repair log and the configured URL. Pure editing and export can be used independently of a repair model.

**Different font appearance:** install the same font on both machines, choose it in the text properties, and check the PDF/PPTX output. System font fallback can change the visible result.

**Unexpected replacement scope:** retain strict mode, review the target list, and use a smaller manual region for mixed-text lines or image-backed wordmarks.
