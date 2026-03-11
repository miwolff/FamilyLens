# User Requirements

## Core

- Users should be able to search their photo library using natural language queries (e.g., "photos from last summer", "pictures with grandma", "birthday party photos", "photos of the beach in Iceland" etc.)
- The application should run entirely on the user's local machine, without uploading photos or metadata to the cloud
- The search results should be accurate and relevant, leveraging metadata and content analysis of the photos
- The application should have a simple and intuitive user interface for searching and browsing photos
- The frontend should look sleek, modern, and professional while prioritizing the photo gallery over interface chrome
- The frontend should keep the top-level controls compact so the photo grids get as much viewport space as possible
- Ongoing and completed indexing status should stay in the shared top header instead of consuming a separate content row
- Cluster navigation and cluster/library summary info should stay in one compact horizontal toolbar row when space allows
- The cluster toolbar should merge library summary info into the direct cluster picker when possible to avoid redundant pills
- The top header should keep a stable height while controls change state, use more unified pill heights, place the Search/Clusters switch next to the FamilyLens title, and place indexing controls further to the right
- The Search/Clusters switch should become slightly more compact on narrower screens, and all top-header pills should use the same standard height
- Indexing status changes must not shift the positions of the Search/Clusters switch, Index Photos button, cluster count picker, or cleanup checkbox, and the first row below the header should keep the same height in Search and Clusters views
- The reserved indexing-status area in the top header should be wide enough to show the full status pill without clipping
- The indexing-status pill in the top header does not need to repeat cluster-count information that is already shown elsewhere, and it should not repeat the active "Indexing..." label that is already shown on the pressed button
- During active indexing, the reserved status area should have enough width that the status pill and cancel button do not collapse into an internal horizontal scrollbar
- The indexing-status pill should omit the indexed-photo counter chip and the progress bar, and the main header controls should remain slightly farther to the right once that status content is shortened
- The header action controls should sit slightly left of their current position without crowding the Search/Clusters switch, and the cancel button inside the indexing-status pill should align vertically with the rest of that pill
- The header action group should be nudged a bit farther left than the current balance while preserving the same control order and spacing logic
- The frontend should avoid redundant navigation and repeated buttons when the same action is already available elsewhere in the UI

## MVP (v0.1)

- Index photos from a user-specified folder on manual command
- Show live indexing progress in the UI with:
  - Progress bar showing current file / total files
  - Percentage completion
  - Elapsed time and estimated time remaining (ETA)
  - Real-time counts of indexed, skipped, error, and removed files
  - Ability to cancel indexing mid-run
- Provide a web app with a search bar for natural language queries
- Display a ranked list of photos most similar to the query, browsable as a gallery
- All components run in Docker containers via Docker Compose
- Must run on a MacBook Air with 8 GB RAM (testing) and a PC with 8 GB GPU (production, ~30,000 photos)
- Supported image formats: JPEG, PNG, Adobe DNG, and Nikon NEF
- Stack: CLIP ViT-B/32 (sentence-transformers), Qdrant, FastAPI, React (Vite + nginx)

### Index Management

- Users can remove stale index entries (files no longer on disk) via a compact "Remove deleted" checkbox on the Index Photos button. This is useful when changing the photo directory path or after deleting photos from disk.
- Users can choose the desired number of clusters in the top header before starting indexing; clicking Index Photos should rebuild clusters using that number, and the default cluster count should be 12.
- Users can index photos from up to 5 separate directories by setting `PHOTOS_DIR`, `PHOTOS_DIR_2` … `PHOTOS_DIR_5` in `.env`. Extra directories are mounted under `/photos_N` in the container and indexed together with the first photos folder.

## v0.2

- Users can browse clusters of visually similar images on a dedicated clusters page in the frontend.
- The application should order clusters from largest to smallest so browsing starts with the biggest cluster and can continue through the next largest clusters one by one.
- Each cluster page should open directly into the full gallery of images assigned to that cluster, sorted so the strongest matches appear first.
- Users should be able to jump directly to any cluster from a compact picker in the cluster toolbar.
- Users should be able to navigate from the search page to the clusters page and back again.
- The backend should rebuild clusters automatically after each indexing run so cluster browsing stays aligned with the current image library.
- Cluster browsing should remain local-first and use the same indexed embeddings already stored for search.

