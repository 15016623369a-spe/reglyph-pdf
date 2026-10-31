# Security and document data

Standard editing uses local OCR and a loopback image-repair service. Installation and initial model downloads use external package/model services. Configuring a remote repair URL sends the crop context and mask to that endpoint; choose endpoints appropriate for your data.

Projects contain original page images, repaired variants, text, and layout metadata. Operation records may contain source/replacement strings and region information. Treat projects, logs, caches, and operation records as document data when sharing them.

The project loader validates manifests and asset paths before replacing the current document. Edit contracts reject stale or out-of-scope operations. These safeguards control document mutation; they do not make arbitrary imported files or remote repair services trustworthy.

Report suspected vulnerabilities using the repository's private vulnerability reporting channel when available, or contact the maintainer through their GitHub profile. Do not put credentials, private documents, exploit samples containing sensitive data, or private repair URLs in a public issue.
