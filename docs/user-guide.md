# User guide

## Prepare a document

Import a PDF or image collection and save a separate `.ipdfedit` project. OCR the current page for a small edit or all pages for a broader operation. OCR adds location and text data; it does not remove letters from the underlying image.

## Replace names and labels

Open **Find and replace** (查找替换), enter the original and replacement text, and select the page scope. Keep **Strict location**, **Clear original background text**, and **Preserve other original content** enabled for a selective replacement workflow.

Preview the matches. Review the original text, proposed replacement, page number, and processing explanation. Uncheck any item you do not want to change. Items marked for review remain unchanged.

Apply the selected changes, inspect the repaired page, and save the project. Use **More → Operation records** to inspect the plan and validation result. If a replacement batch fails or is canceled, it restores the previous text, background mapping, and undo/redo history.

## Resolve a review item

A mixed-text OCR line may contain the name you want to replace but lack its exact word coordinates. Low-confidence text also requires review. Navigate to that page, zoom in, and select a region tightly around the intended lettering. Erase only that region, add the replacement text, then check its font, color, size, and placement. Avoid including neighboring dates, captions, rules, or other lettering in the mask.

For a photograph or textured surface, inspect the reconstruction after repair. Undo and refine the region if its visual quality is unsuitable. Strict background validation protects the surrounding page; it does not grade the repaired pixels inside the selection.

## Adjust typography

Select a text box to change its content and properties. Move it on the canvas or resize its bounding box. Use **Uniform font sizes** to set consistent sizes for selected text roles such as headings, body copy, or footers. Merge lines of the same paragraph before changing a paragraph's layout.

A brand-only replacement preserves other original content as image-backed page pixels. Reconstruct additional text layers only when you intend to edit those areas. Full-page reconstruction is a separate editing operation with a larger scope.

## Recover and export

Save `.ipdfedit` to keep the original assets, repaired variants, and editable text. Automatic backups are accessible through the **More** menu. Undo/redo supports editing changes within the active session.

Export PDF for distribution and native-text PowerPoint for presentation editing. Check the final document, especially text on photographs and fonts that may differ between computers.

## Resource use

Reuse OCR when only changing replacement copy, work on the relevant pages, and avoid repeated full-page repair for a small label change. Identical repair inputs reuse the bounded cache. Clear the repair cache after changing the repair model or endpoint behavior.

The CPU thread budget can be adjusted from 1 to 4 using `IPDF_CPU_THREADS`. M1/M2-class machines and higher configurations use the same processing pipeline; page size and repair complexity determine the work required.
