import csv
import json
import sys

def convert_stops_to_geojson(stops_file, output_file):
    features = []
    
    with open(stops_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            if 'stop_lat' in row and 'stop_lon' in row and row['stop_lat'] and row['stop_lon']:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            float(row['stop_lon']), 
                            float(row['stop_lat'])
                        ]
                    },
                    "properties": {
                        "stop_id": row.get("stop_id", ""),
                        "stop_name": row.get("stop_name", ""),
                        "stop_desc": row.get("stop_desc", ""),
                        "zone_id": row.get("zone_id", ""),
                        "stop_url": row.get("stop_url", "")
                    }
                }
                features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
    
    print(f"GeoJSON file saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py stops.txt output.geojson")
    else:
        convert_stops_to_geojson(sys.argv[1], sys.argv[2])
