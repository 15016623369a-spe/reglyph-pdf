# Architecture

ReGlyph PDF keeps document state, a visual editing layer, and repair execution separate. The same portable project format is used across supported desktop platforms.

## Components

| Module | Responsibility |
| --- | --- |
| `editor.py` | Desktop workflow, text properties, project actions and export orchestration |
| `engine.py` | Graphics canvas, page operations, OCR workers and image-repair workers inherited and extended from the upstream editor |
| `exact_edit.py` | GUI-independent replacement plans, document fingerprints, validation and strict mask compositing |
| `precision_ui.py` | Review dialog, transactional replacements, output comparison and operation records |
| `batch_clean.py` | Solid-background detection, bounded context batching and content-addressed repair cache |
| `ocr_engine.py` | PaddleOCR adapter with recognition confidence and CPU configuration |
| `workflow.py` | Portable project persistence, text operations and typography roles |
| `ppt_export.py` | PowerPoint generation and layout handling |
| `launcher.py` | Editing environment selection and owned local repair-service lifecycle |
| `platform_config.py` | Platform data folders, model discovery and numerical thread configuration |
| `bootstrap.py` | Reproducible installation of isolated editing and repair environments |

## Document pipeline

PDF pages are rasterized into page assets. OCR supplies text, confidence, and bounding regions. An editable model stores text geometry and styling while the original image remains available for comparison. A repaired image is stored as a separate page variant instead of replacing the original.

The `.ipdfedit` archive contains a versioned JSON manifest, original page assets, optional repaired assets, text boxes, selected regions, and navigation state. Saving uses a temporary archive followed by an atomic replacement. Opening validates the archive and paths before replacing the active document.

## Strict replacement contract

A plan includes a document fingerprint, explicit operation parameters, page scope, source and replacement strings, target identifiers, character offsets, permitted regions, and review items. The contract module treats OCR content as data, including any instructions embedded in a document.

Automatic whole-box replacement requires a confident recognition result or a reviewed target. A substring requires actual word-span coordinates; the engine does not estimate proportional character positions. The desktop strict workflow conservatively reviews mixed-text boxes.

Before a strict replacement is committed, the implementation checks the input snapshot, the expected text/layout result, and background pixels outside the allowed regions. Canceled, failed, or invalid replacement transactions restore the document and history. Successful transactions write a JSON audit record under the application data directory.

The allowed region controls which pixels can change. It does not evaluate whether a reconstruction inside that region looks convincing, nor prove that OCR found every occurrence. The review step and visual inspection remain part of the editing workflow.

## Repair execution

Simple solid-color surrounds use local reconstruction. Textured regions use LaMa through IOPaint. Requests contain cropped context plus a binary edit mask; the returned image is composited only through that mask. Neighboring requests may share a bounded context window, while their permitted masks remain an exact union rather than a filled bounding rectangle.

Cache keys include endpoint identity, image content, dimensions, and mask content. Repeated identical repairs can reuse local results. Cache eviction affects speed, not saved project assets. A single repair endpoint processes its crop queue sequentially.

## Output model

The PDF exporter combines a repaired background image with text layers. PPTX exports use native text boxes. Unreconstructed page content remains part of the background image. Perspective transforms and system fonts should be checked in the destination format because PDF and presentation renderers have different capabilities.

## Runtime boundaries

The editing environment contains PySide6, PaddleOCR/PaddlePaddle, OpenCV, NumPy, Pillow, PyMuPDF, and python-pptx. The repair environment contains IOPaint, LaMa/PyTorch, and its separate compatibility constraints. The launcher passes a bounded CPU thread budget before numerical libraries are imported and uses loopback networking for the repair endpoint.
