#!/usr/bin/env bash
# Release build of the app with the backend URL baked in.
#
#   tool/build_release.sh              # APK  -> build/app/outputs/flutter-apk/app-release.apk
#   tool/build_release.sh appbundle    # AAB  -> build/app/outputs/bundle/release/app-release.aab
#   API_BASE_URL=https://… tool/build_release.sh
#
# Signs with the upload key in android/key.properties when that file exists,
# otherwise with the debug key (Gradle prints a warning). See mobile/README.md.
set -euo pipefail
cd "$(dirname "$0")/.."

target="${1:-apk}"
shift || true
api="${API_BASE_URL:-https://3-108-52-61.sslip.io}"

if [ -f android/key.properties ]; then
  echo "Signing with the upload key (android/key.properties)."
else
  echo "android/key.properties not found: signing with the DEBUG key (fine for testing, not for Play)."
fi

exec flutter build "$target" --release --dart-define=API_BASE_URL="$api" "$@"
