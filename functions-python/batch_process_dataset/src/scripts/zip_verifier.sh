# Inspect headers and redirect chain (no file saved)
curl -ILv "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip"

# Download the body (ZIP) — no -I, follow redirects, set UA
curl -L --fail -A "Mozilla/5.0" \
  -o /tmp/stm.zip \
  "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip"

# Sanity checks
file /tmp/stm.zip
python - <<'PY'
import zipfile
print("is_zip:", zipfile.is_zipfile("/tmp/stm.zip"))
PY
