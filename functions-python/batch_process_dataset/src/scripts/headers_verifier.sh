# This is to inspect what the server actually returned: Save headers to see final status and Content-Type
# If Content-Type is text/html or status is 30x/403, you’re not getting the ZIP.
curl -sSL --fail \
  -D /tmp/headers.txt \
  -A "Mozilla/5.0" \
  -o /tmp/stm.zip \
  "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip"

echo "== Headers ==" && cat /tmp/headers.txt
file /tmp/stm.zip
hexdump -C /tmp/stm.zip | head
