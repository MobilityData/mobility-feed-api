# Download while capturing headers and using a browser-like client identity
#- Valid ZIP should begin with “PK..” (hex 50 4b 03 04 or 50 4b 05 06).
#- If you see “<!DOCTYPE” or “<html…”, you got an HTML page (redirect, consent, 403, etc.).
curl -sSL --fail \
  -D /tmp/headers.txt \
  -A "Mozilla/5.0" \
  -H "Referer: https://www.stm.info/" \
  -H "Accept: */*" \
  -o /tmp/stm.zip \
  "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip"

echo "== Headers ==" && cat /tmp/headers.txt
echo "== Size ==" && wc -c /tmp/stm.zip
echo "== First 64 bytes ==" && hexdump -C /tmp/stm.zip | head -n 4
