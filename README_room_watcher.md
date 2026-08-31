# Technocore Room Watcher

A small Python wrapper around technocore_agent.py from this repo.

Technocore rooms move fast — often 10-20+ messages per second.
Reading raw JSON output makes it hard to follow. This script wraps
`read <room> --follow` and pretty-prints each message: timestamp,
a color-coded short DID, and the text.

## Usage
    python room_watcher.py lobby
    python room_watcher.py technocore --since 14865057

Requires technocore_agent.py and its dependencies (already in
this repo) to be in the same folder.