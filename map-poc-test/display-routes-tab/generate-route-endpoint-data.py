import csv
import json
import argparse

def load_csv(file_path, key_column):
    """Loads a CSV file into a dictionary with key_column as the key."""
    data = {}
    with open(file_path, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            data[row[key_column]] = row
    return data

def process_gtfs(calendar_file, trips_file, routes_file, output_file):
    """Processes GTFS files and generates a JSON output."""
    calendar_data = load_csv(calendar_file, 'service_id')
    trips_data = load_csv(trips_file, 'trip_id')
    routes_data = load_csv(routes_file, 'route_id')
    
    route_info = {}
    
    for trip in trips_data.values():
        service_id = trip['service_id']
        route_id = trip['route_id']
        
        if service_id not in calendar_data or route_id not in routes_data:
            continue
        
        calendar_entry = calendar_data[service_id]
        route_entry = routes_data[route_id]
        
        if route_id not in route_info:
            route_info[route_id] = {
                'routeId': route_id,
                'routeName': route_entry.get('route_long_name', '') or route_entry.get('route_short_name', ''),
                'color': f"#{route_entry.get('route_color', '000000')}",
                'textColor': f"#{route_entry.get('route_text_color', 'ffffff')}",
                'routeType': route_entry.get('route_type', ''),
                'startDate': calendar_entry['start_date'],
                'endDate': calendar_entry['end_date'],
                'monday': calendar_entry['monday'] == '1',
                'tuesday': calendar_entry['tuesday'] == '1',
                'wednesday': calendar_entry['wednesday'] == '1',
                'thursday': calendar_entry['thursday'] == '1',
                'friday': calendar_entry['friday'] == '1',
                'saturday': calendar_entry['saturday'] == '1',
                'sunday': calendar_entry['sunday'] == '1'
            }
    
    with open(output_file, 'w', encoding='utf-8') as json_file:
        json.dump(list(route_info.values()), json_file, indent=4)

def main():
    parser = argparse.ArgumentParser(description='Process GTFS files and generate JSON output.')
    parser.add_argument('calendar', help='Path to calendar.txt')
    parser.add_argument('trips', help='Path to trips.txt')
    parser.add_argument('routes', help='Path to routes.txt')
    parser.add_argument('output', help='Path to output JSON file')
    args = parser.parse_args()
    
    process_gtfs(args.calendar, args.trips, args.routes, args.output)

if __name__ == '__main__':
    main()
