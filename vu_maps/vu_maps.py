import json
import os
import requests

from gmplot import gmplot
from shapely import geometry, intersection_all, MultiPolygon, Polygon
from shapely.ops import unary_union

def round_coord(coord):
    return [round(coord[0], 2), round(coord[1], 2)]

def load_cache(cache_folder):
    cache = {}
    count = 0
    for file in os.listdir(cache_folder):
        with open(cache_folder + '/' + file, 'r') as f:
            location = json.load(f)
        long, lat = round_coord(location['properties']['center'])
        cache[(long, lat, location['properties']['value'])] = location
        count += 1
    return cache, count

def compute_isochrones(desired_isochrones, cache_folder, api_key):
    # desired_isochrones is of the form [([longitude, latitude], time), ...]
    cache, count = load_cache(cache_folder)
    
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': api_key,
        'Content-Type': 'application/json; charset=utf-8'
    }

    isochrones = []
    isochrones_to_request = []

    for desired_isochrone in desired_isochrones:
        try:
            location, time = desired_isochrone
            long, lat = round_coord(location)
            isochrone = cache[(long, lat, time)]['geometry']['coordinates']
            print('found in cache')
            isochrones.append((long, lat, time, isochrone))
        except:
            print('not found in cache')
            isochrones_to_request.append(desired_isochrone)
            
    locations_per_time = {}
    for iso in isochrones_to_request:
        location, time = iso
        if time in locations_per_time:
            locations_per_time[time].append(location)
        else:
            locations_per_time[time] = [location]
    for time in locations_per_time:
        for locations in [locations_per_time[time][i:i+5] for i in range(0, len(locations_per_time[time]), 5)]:
            body = {"locations":locations,"range":[time]}
            call = requests.post('https://api.openrouteservice.org/v2/isochrones/driving-car', json=body, headers=headers)
            print(call.status_code, call.reason)
            if call.status_code != 200:
                print(call.text)
            d = call.json()
            for i, isochrone in enumerate(d['features']):
                long, lat = locations_per_time[time][i]
                isochrones.append((long, lat, time, isochrone['geometry']['coordinates']))
                # cache results
                filename = cache_folder + "/loc" + str(count) + ".json"
                with open(filename, 'w') as f:
                    json.dump(isochrone, f)
                count+=1
    return isochrones

def init_gmap(center, zoom):
    return gmplot.GoogleMapPlotter(center[1], center[0], zoom)

def save_gmap(gmap, filename):
    gmap.draw(filename)
    
def get_union(shapely_objects):
    return unary_union(shapely_objects)
    
def get_intersection(shapely_objects):
    return intersection_all(shapely_objects)
    
def isochrone_to_shapely(isochrone):
    return geometry.Polygon(isochrone[3][0])

def plot_isochrone(gmap, isochrone, color):
    long, lat, _, coords = isochrone
    longs, lats = zip(*coords[0])
    # Add a marker for the center of the isochrone
    gmap.marker(lat, long, color)

    # Add a polygon representing the isochrone
    gmap.polygon(lats, longs, color=color, edge_width=10)

def plot_shapely(gmap, isochrone, color):
    long, lat = list(isochrone.centroid.coords)[0]
    gmap.marker(lat, long, color)
    
    longs, lats = isochrone.exterior.coords.xy
    gmap.polygon(lats, longs, color=color, edge_width=10)

def plot_intersection(gmap, intersection, color):
    if type(intersection) == Polygon:
        longs, lats = intersection.exterior.coords.xy
        gmap.polygon(lats, longs, color=color, edge_width=10)
    elif type(intersection) == MultiPolygon:
        for subregion in intersection.geoms:
            longs, lats = subregion.exterior.coords.xy
            gmap.polygon(lats, longs, color=color, edge_width=10)
    else:
        raise ValueError('Invalid type for intersection')