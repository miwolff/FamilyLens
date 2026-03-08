# User Requirements

## Core

- Users should be able to search their photo library using natural language queries (e.g., "photos from last summer", "pictures with grandma", "birthday party photos", "photos of the beach in Iceland" etc.)
- The application should run entirely on the user's local machine, without uploading photos or metadata to the cloud
- The search results should be accurate and relevant, leveraging metadata and content analysis of the photos
- The application should have a simple and intuitive user interface for searching and browsing photos

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
- Supported image formats: JPEG and PNG
- Stack: CLIP ViT-B/32 (sentence-transformers), Qdrant, FastAPI, React (Vite + nginx)

### Index Management

- Users can remove stale index entries (files no longer on disk) via a "Remove deleted files from index" checkbox on the Index Photos button. This is useful when changing the photo directory path or after deleting photos from disk.
- Users can index photos from up to 5 separate directories by setting `PHOTOS_DIR`, `PHOTOS_DIR_2` … `PHOTOS_DIR_5` in `.env`. Extra directories are mounted under `/photos_N` in the container and indexed together with the first photos folder.

