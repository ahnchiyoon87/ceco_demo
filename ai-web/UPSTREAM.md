# Frontend reuse

Source: `https://github.com/uengine-oss/ontology-studio`
Revision: `6a229be8dcce2aeb533ecdba360b5b4564ffb777`
Imported directory: `frontend/`.

The user authorized reuse and rebranding of their company's code for this
education and exhibition project on 2026-09-21. Third-party notices remain
applicable.

The manufacturing workspace shell, information hierarchy and styling are new.
The original Vue/Cytoscape OntologyGraphPanel is actively reused, loaded on
demand. Its new readOnly option suppresses mutation controls and guards mutation
handlers for the operations knowledge browser. Natural-language graph search is
hidden there until the model path is connected. The upstream editing and chat
components remain available for integration; their presence does not mean those
workflows are wired into the manufacturing workspace.

Verification on 2026-09-21: Vite production build passed. The local development
proxy returned HTTP 200 for actual incident and graph APIs. Visual inspection
and end-to-end UI interaction have not yet been completed; the browser connector
reported no available browser. No demonstration screenshot has been claimed.

## Third-party license texts

`public/THIRD-PARTY-NOTICES.txt` contains verbatim LICENSE/NOTICE files for the
25 installed production dependencies selected from package-lock.json. Regenerate
with `python collect_notices.py` after `npm ci` when the lockfile changes, then
rebuild. Missing license files cause generation to fail without overwriting the
previous output. The file is served at `/THIRD-PARTY-NOTICES.txt` in the web build.
It covers frontend dependencies only, not backend/container packages or the
separate company-owned upstream reuse authorization above.
