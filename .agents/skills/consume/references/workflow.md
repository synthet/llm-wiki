# Downloads ingest and pipeline workflow

## Discovery rules

The pipeline discovers download directories when:

- A folder's name is `Downloads`, `Download`, or ends with `-downloads` (case-insensitive).
- The path resolves within an `allowed_roots` entry in `.llmwiki/config.yaml`, or is explicitly passed via `--dir <path>`.
- User home `~/Downloads` is automatically included when within `allowed_roots`.

## Supported document formats

- **Markdown**: `.md`, `.markdown`
- **Plaintext & Specs**: `.txt`
- **PDF Documents**: `.pdf`
- **Structured Data**: `.json`, `.csv`, `.html` (when specified in `--extensions`)

## Operator & agent playbook

1. **Scan & Plan**:
   ```bash
   uv run python scripts/wiki_ingest_pipeline.py --dir "D:/Downloads" --extensions .md,.txt,.pdf
   ```
2. **Execute Ingest & Compile**:
   ```bash
   uv run python scripts/wiki_ingest_pipeline.py --dir "D:/Downloads" --run --auto-compile --render
   ```
3. **Verify and Clean**:
   ```bash
   uv run python scripts/wiki_ingest_pipeline.py --dir "D:/Downloads" --run --cleanup
   ```
4. **Audit and Validate**:
   ```bash
   uv run llmwiki validate --json
   uv run llmwiki stats
   ```

## Safety guarantees

- **Zero data loss on failure**: Unparseable or uningested files are skipped and never deleted.
- **Content-addressed verification**: Files are only unlinked from disk if their exact SHA-256 byte digest is present in `.llmwiki/objects/` and recorded in `source_revisions`.
- **Review separation**: All claims generated during batch ingest enter with `candidate` status until explicitly approved by a human reviewer.
