# Photo burst culling by eye sharpness - Driftara/Vexlum stack (2026-09-20)

Local notes from ranking a 60-frame bird burst by eye sharpness in the `image-scoring-gallery` /
`image-scoring-backend` stack. Treat as internal evidence.

## Workstation layout observed

- Gallery repo: `D:\Projects\image-scoring-gallery`; backend repo: `D:\Projects\image-scoring-backend` (siblings)
- Gallery `config.json` sets `database.engine: postgres` against `127.0.0.1:5432`, database `image_scoring`
- Backend `webui.lock` recorded `{"pid": 39, "port": 7860}` while nothing listened on 7860 - the lock file
  goes stale and is not proof the API is running; verify with a live port check before trusting it
- With the FastAPI backend down, the Postgres store remains directly queryable, so DB-backed triage does not
  depend on the API being up
- No `psql` on PATH; the gallery's bundled `pg` node module under `node_modules/pg` works as a query path

## Database schema facts observed

- `images.file_path` holds WSL-style paths (`/mnt/d/Photos/...`); `images.thumbnail_path_win` holds the
  Windows form (`D:\Projects\image-scoring-backend\thumbnails\<xx>\<md5>.jpg`)
- `images` has no `width` / `height` columns
- `image_model_scores` columns are `image_id`, `model_name`, `raw_score`, `normalized`, `status`,
  `is_shadow`, `model_version`, `scored_at` - there is **no** `score` column
- `model_name` values present: `arniqa`, `ava`, `clip_quality_v0`, `koniq`, `liqe`, `paq2piq`, `spaq`, `topiq`
- `images.bird_bbox` is a JSON column carrying `x1/x2/y1/y2`, `conf`, `img_w`, `img_h`, `area_frac`

## Why stored scores and boxes did not discriminate within a burst

- Per-image model scores are whole-frame quality estimates and are nearly flat across a burst of the same
  scene: across 60 frames SPAQ spanned 72-77 and LIQE 74-95 with no correspondence to eye sharpness
- Therefore stored model scores cannot rank frames within a burst; they rank scenes, not focus accuracy
- `bird_bbox` was unusable for a bird perched lengthwise on a lit branch: several boxes spanned nearly the
  whole frame (e.g. `x1=140,x2=5386` on a 5392-wide image at `conf=0.66`) because the detector locked onto
  the branch rather than the bird
- Consequence: subject localisation for focus scoring had to be recomputed, not read from the DB

## Extracting pixels without decoding RAW

- Nikon Z8 NEF files carry a full-resolution embedded JPEG preview: `exiftool -b -JpgFromRaw <file>.NEF`
  yielded 5392x3592 JPEGs of roughly 2 MB each
- This avoids a RAW development step entirely for sharpness/triage work; 63 previews extracted to ~114 MB
- `exiftool -s -PreviewImageSize` reported nothing for these files while `-JpgFromRawLength` did, so probe
  with `-JpgFromRawLength` to confirm preview availability

## Template matching pitfalls when localising the subject

- `cv2.matchTemplate` with `TM_CCOEFF_NORMED` produces spurious high peaks on smooth low-variance regions
  (open sky, out-of-focus bokeh); normalised correlation is unstable where local variance approaches zero
- Suppressing candidate windows whose local standard deviation is below ~0.45x the template's own std
  removes the flat-region false peaks; local std is computable cheaply with `cv2.boxFilter` on the image
  and its square
- After flat-region suppression, high-texture **bark** became the next false-positive class, scoring above
  the true subject on Laplacian-based sharpness because lichen-covered bark is finely textured
- Sequential frame-to-frame tracking drifted irrecoverably once a single frame lost lock, since each bad hit
  re-centred the next search window
- Global `cv2.phaseCorrelate` alignment failed here (response ~0.00) despite constant focal length, so a
  whole-frame translation estimate was not a usable shortcut
- What worked: anchor each frame's search window on the verified eye position of a temporally adjacent
  frame, then confirm every accepted crop visually before trusting its score
- Raw template-match confidence was a poor validity signal: genuine locks scored 0.93-1.00 but false locks
  on sky and bark also sat at 0.55-0.62, so a confidence threshold alone could not separate them

## Measuring focus on the eye

- Burst was shot at constant 600 mm and 1/2004 s, so subject scale was constant and only translation varied
- ISO was **not** constant across the burst (1400-2200); sensor noise inflates Laplacian variance, which
  biases a naive sharpness ranking toward the noisier high-ISO frames
- Pre-blurring the crop with a Gaussian of sigma 1.0 before taking Laplacian variance suppresses per-pixel
  noise while retaining defocus-scale structure, and reordered the ranking so the two lowest-ISO frames rose
  to the top
- Local contrast also varies between frames; comparing raw Laplacian variance across frames of differing
  contrast is only safe when the lower-contrast frames still score higher, as happened here

## Library gotcha

- `cv2.Laplacian(src, ddepth, 3)` silently does the wrong thing: the third positional parameter is `dst`,
  not `ksize`. Passing the kernel size positionally yielded variance values of 0-27 instead of ~1500-1800.
  Always pass `ksize=` by keyword.

## Data quality observation

- Image ID 234771 (`DSC_7774.NEF`) carried keyword `species:Eastern Screech-Owl`, but the subject is a
  Common Nighthawk (cryptic plumage, white throat patch, long primaries, roosting lengthwise along the
  branch). At least that record's species tag is wrong.

## Outcome for this burst

- Gallery image IDs are not ordered by filename: ID range 234709-234771 covered `DSC_7706`-`DSC_7774`
  non-monotonically, and four frames of the same burst (`DSC_7768`, `7769`, `7771`, `7773`) fell **outside**
  that ID range at IDs 234772-234775
- Selecting an ID range is therefore an unreliable way to select a burst; select by folder plus filename
- Sharpest eye in range: `DSC_7774` (ID 234771), then `DSC_7772` (234766) and `DSC_7766` (234767);
  `DSC_7773` (ID 234775, outside the queried range) would have ranked second overall
- The two top frames were also the only ISO 1400 frames, so they were simultaneously the sharpest and the
  cleanest
