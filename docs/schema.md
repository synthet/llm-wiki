# Page & frontmatter schema

Every wiki page is a Markdown file with a YAML frontmatter block, stored under
`wiki/pages/`. The frontmatter is the machine-readable part the toolkit indexes
and validates; the Markdown body is a human-readable projection.

## Fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `id` | ✅ | string | Canonical, opaque, **unique** identity (e.g. `entity:ckan`). Stable across renames. |
| `title` | ✅ | string | Human-readable name. |
| `type` | ✅ | enum | `entity` \| `topic` \| `note` \| `index`. |
| `status` | ✅ | enum | `candidate` \| `reviewed` \| `disputed` \| `stale` \| `superseded` \| `retracted`. |
| `slug` | – | string | Filename-friendly alias; not identity. Defaults to filename. |
| `aliases` | – | list | Alternate names/ids the page resolves from (used by `[[links]]`). |
| `tags` | – | list | Free-form labels; indexed for search. |
| `created`, `updated` | – | datetime | ISO-8601. |
| `sources` | – | list | See below. Required in practice for reviewed entity/topic pages. |
| `claims` | – | list | Atomic, checkable statements with evidence. See below. |
| `freshness` | – | map | `checked_at`, `expires_at`, `stale`. |
| `rights` | – | map | `license_expression`, `redistribution_allowed`. |

### `sources[]`
```yaml
sources:
  - id: source:okf-repo          # referenced by claim evidence
    uri: https://github.com/GoogleCloudPlatform/open-knowledge-format
    digest: sha256:<hex>         # content-addressed source revision
    rights: apache-2.0
```

### `claims[]`
```yaml
claims:
  - id: claim:okf-is-format
    text: A precise, checkable statement extracted from a source.
    status: reviewed             # candidate|reviewed|disputed|superseded|retracted
    confidence: 0.9
    evidence:
      - source_id: source:okf-repo   # must exist in this page's `sources`
        locator: {type: line-range, start: 10, end: 20}
```

## Review states

| state | meaning |
|---|---|
| `candidate` | LLM-generated, not yet reviewed (**default** for new content). |
| `reviewed` | Approved by a human or an explicit policy gate. |
| `disputed` | Competing claims retained; not silently overwritten. |
| `stale` | A dependent source changed; needs re-checking. |
| `superseded` | Replaced by a newer claim; kept for audit. |
| `retracted` | Withdrawn; tombstoned rather than deleted. |

## Invariants enforced by `llmwiki lint`
1. Frontmatter is valid YAML and carries `id`, `title`, `type`, `status`.
2. `type`/`status` use the controlled vocabularies above.
3. `id` and `slug` are unique across the wiki.
4. Every `[[Wikilink]]` resolves to a page (by id, slug, title or alias).
5. `reviewed`/`disputed` claims carry `evidence`; evidence references a listed
   source (`--strict` promotes the missing-evidence warning to an error).
6. Source digests are `sha256:` values; freshness `expires_at` is in the future.
7. Redistributable pages declare a license.

Run `llmwiki rules` for the full rule list.
