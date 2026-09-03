#!/bin/bash
# Spoken edition — run this yourself so your API key never leaves your machine.
#
#   export OPENAI_API_KEY='sk-...'        # once per terminal session
#   ./tools/publish_audio.sh              # today's paper in the default voice
#   ./tools/publish_audio.sh sage         # ...or in a named voice
#   ./tools/publish_audio.sh --sample     # top story in onyx AND sage, to compare
#
set -e
cd "$(dirname "$0")/.."

if [ -z "$OPENAI_API_KEY" ]; then
  echo "OPENAI_API_KEY is not set."
  echo "Run:  export OPENAI_API_KEY='your-key-here'   then try again."
  exit 1
fi

if [ "$1" = "--sample" ]; then
  python3 tools/make_audio.py --sample
  echo
  echo "Tap either link above to compare. Nothing was published to the paper."
  exit 0
fi

VOICE="${1:-onyx}"
echo "Generating today's spoken edition in '$VOICE' …"
python3 tools/make_audio.py --voice "$VOICE"

git add audio/manifest.json
git commit -q -m "Spoken edition ($VOICE)" || { echo "nothing new to commit"; exit 0; }
git pull --rebase -q
git push -q
echo
echo "Published. Open the paper on your phone and press the headphone button:"
echo "  https://vivekcpa1116-cmd.github.io/deccan-ledger/?v=$(date +%H%M)"
