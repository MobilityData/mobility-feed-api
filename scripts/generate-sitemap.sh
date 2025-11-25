#!/bin/bash

# Array of IDs
gtfs_id=(

)

gtfs_rt_ids=(
 
)

gbfs_ids=(

)

# Base URL
base_url_gtfs="https://mobilitydatabase.org/feeds/gtfs"
base_url_gtfs_rt="https://mobilitydatabase.org/feeds/gtfs_rt"
base_url_gbfs="https://mobilitydatabase.org/feeds/gbfs"

# Output folder and file
output_folder="web-app/public"
sitemap_file="${output_folder}/sitemap.xml"
lastmod=$(date +%Y-%m-%d) # Use current date as the last modified date

# Ensure the output folder exists
mkdir -p "$output_folder"

# Generate sitemap header
cat <<EOL > "$sitemap_file"
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url>
    <loc>https://mobilitydatabase.org/feeds/</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
</url>
EOL

# Add each URL to the sitemap
for id in "${gtfs_id[@]}"; do
  url="${base_url_gtfs}/${id}"

  cat <<EOL >> "$sitemap_file"
  <url>
    <loc>${url}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
EOL
done
# Add each URL to the sitemap
for id in "${gtfs_rt_ids[@]}"; do
  url="${base_url_gtfs_rt}/${id}"

  cat <<EOL >> "$sitemap_file"
  <url>
    <loc>${url}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
EOL
done
# Add each URL to the sitemap
for id in "${base_url_gbfs[@]}"; do
  url="${base_url_gbfs}/${id}"

  cat <<EOL >> "$sitemap_file"
  <url>
    <loc>${url}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
EOL
done

# Close the sitemap
echo "</urlset>" >> "$sitemap_file"

echo "Sitemap generated successfully: $sitemap_file"
