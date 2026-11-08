# User Requirements

## Goals

- Users search their personal photo library with natural-language queries
  (e.g. "birthday party", "pictures with grandma", "beach in Iceland").
- Everything runs on the user's machine. Photos and metadata are never
  uploaded anywhere.
- Results are relevant and ranked, based on the visual content of the photos.

## Platform

- All components run in Docker containers, started with Docker Compose.
- Stack: CLIP ViT-B/32 (sentence-transformers), Qdrant, FastAPI, React (Vite)
  served by nginx.
- Runs on a laptop with 8 GB RAM and scales to a library of about 30,000
  photos.
- Supported formats: JPEG, PNG, Adobe DNG and Nikon NEF.

## Indexing (v0.1)

- Users start indexing manually from the UI.
- Up to five photo folders can be configured (`PHOTOS_DIR`, `PHOTOS_DIR_2`
  … `PHOTOS_DIR_5`). They are mounted read-only at `/photos/1` …
  `/photos/5` and indexed together.
- Already-indexed photos are skipped, so repeated runs only process new files.
- An optional "Remove deleted" setting removes index entries for files that no
  longer exist on disk.
- While indexing, the UI shows live progress: processed/total files,
  percentage, elapsed time, estimated time remaining, and counts of skipped,
  failed and removed files.
- Users can cancel a running indexing job.

## Search (v0.1)

- A search bar accepts a natural-language query.
- Results are shown as a gallery of photos ranked by similarity, each with its
  match score.

## Clusters (v0.2)

- Clusters of visually similar photos are rebuilt automatically after every
  indexing run, using the embeddings already stored for search.
- Users choose the number of clusters (default 12) before starting indexing.
- A dedicated Clusters page lists clusters from largest to smallest.
- Each cluster opens directly into its full gallery, with the most typical
  photos first.
- Users can step to the previous/next cluster or jump to any cluster from a
  picker.
- Users can switch between the Search and Clusters pages at any time.

## User interface

- The design is clean and modern and gives the photo galleries as much screen
  space as possible.
- A single compact header contains the app title, the Search/Clusters switch,
  the indexing controls (Index Photos, cluster count, Remove deleted) and the
  indexing status.
- The header keeps a stable layout: status changes during indexing do not
  move other controls or change the height of the content below.
- The indexing status is shown only once in the header and does not repeat
  information already visible elsewhere (e.g. the cluster count or the
  "Indexing…" button label).
- The cluster toolbar fits in a single row where space allows and combines
  navigation, the cluster picker and library totals.
- The UI avoids duplicate controls for the same action.
