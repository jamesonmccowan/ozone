import numpy as np  # useful for many scientific computing in Python
import pandas as pd # primary data structure library
import folium # !conda install -c conda-forge folium=0.5.0 --yes
import os
import math

import io
from PIL import Image
import geckodriver_autoinstaller
geckodriver_autoinstaller.install()


# load the data from the files
data = {}
file_list = os.listdir('./data/')

for f in file_list:
    if 'L3_ozone_omi_2004' in f: # get records only for the year 2004
    # if f[0] == 'L': # get all records
        with open('./data/{0}'.format(f)) as data_file:
            data[f] = data_file.read()


# parse the files into points
def parse_data(data_str):
    # start by parsing the data string's header
    first  = data_str.split("\n")[0]  # " Day: 275 Oct  1, 2004    OMI TO3    STD OZONE    GEN:12:096 Asc LECT: 01:49 pm "
    second = data_str.split("\n")[1]  # " Longitudes:  360 bins centered on 179.5  W  to 179.5  E   (1.00 degree steps)  "
    third  = data_str.split("\n")[2]  # " Latitudes :  180 bins centered on  89.5  S  to  89.5  N   (1.00 degree steps)  "

    day = first[10:22]
    long_start = float(second[35:40])
    long_start = -long_start if second[42:43] == 'W' else long_start
    long_stop  = float(second[48:53])
    long_stop  = -long_stop if second[55:56] == 'W' else long_stop
    long_step  = float(second[60:64])
    long_bins  = int(second[14:17])

    lat_start = float(third[35:40])
    lat_start = -lat_start if third[42:43] == 'S' else lat_start
    lat_stop  = float(third[48:53])
    lat_stop  = -lat_stop if third[55:56] == 'S' else lat_stop
    lat_step  = float(third[60:64])
    lat_bins  = int(third[14:17])

    # next, get all the points into an array
    # lines are 76 characters long, start with a space, and have up to 25 bins
    # bins have 3 characters representing 1 int
    # lat comes after the last bin, with 3 characters of spaces
    # the actual lat value starts 9 characters after the last bin and is 6 characters long
    # "   lat =  -89.5"

    points = []
    block_size = math.ceil( (long_bins * 3) / 75 )
    lat_range  = np.arange(lat_start, lat_stop+lat_step, lat_step)
    long_range = np.arange(long_start, long_stop+long_step, long_step)
    max_score = 0
    min_score = 0
    max_point = {}

    for lat_pos in range(0, lat_bins):
        block = data_str.split("\n")[3 + (lat_pos * block_size):3 + ((lat_pos+1) * block_size)]
        lat = lat_range[lat_pos]
        for long_pos in range(0, long_bins):
            long = long_range[long_pos]
            line = block[math.floor(long_pos/25)]
            point = {
                'Latitude':  lat,
                'Longitude': long,
                'score': int(line[1+(long_pos % 25)*3:1+((long_pos % 25)+1)*3]),
                'color': '#ffffff'
            }
            if point['score'] > max_score:
                max_score = point['score']
                max_point = point
            if point['score'] < min_score:
                min_score = point['score']

            points.append(point)

    return {
        "points": points,
        "max": max_score,
        "min": min_score,
        "day": day,

        "long_start": long_start,
        "long_start": long_start,
        "long_stop":  long_stop,
        "long_stop":  long_stop,
        "long_step":  long_step,
        "long_bins":  long_bins,

        "lat_start":  lat_start,
        "lat_start":  lat_start,
        "lat_stop":   lat_stop,
        "lat_stop":   lat_stop,
        "lat_step":   lat_step,
        "lat_bins":   lat_bins,
    }

points = {}
for k in data:
    points[k[13:21]] = parse_data(data[k])


## color the points
# 1. red (#FF0000)
# 2. yellow (#FFFF00)
# 3. green (#00FF00) (safe)
# 4. turquoise (#00FFFF)
# 5. blue (#0000FF)
def score_to_color(score, safe_score, max_score):
    color = ""

    if max_score < safe_score:
        max_score = safe_score

    if score <= 0: # score should never be 0 or negative, show error state
        color = "#000000"

    elif score < safe_score / 2: # red to yellow (#FF0000 to #FFFF00)
        a = 255 * score / (safe_score / 2) # value between 0 and 256
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#FF" + (hex(a)[-1]) + (hex(b)[-1]) + "00"

    elif score < safe_score: # yellow to green (#FFFF00 to #00FF00)
        range_start = safe_score / 2
        range_end = safe_score
        true_range = range_end - range_start
        a = 255 * (1 - (score - range_start) / true_range) # value between 256 and 0
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#" + (hex(a)[-1]) + (hex(b)[-1]) + "FF00"

    elif score < ((max_score-safe_score) / 2) + safe_score: # green to turquoise (#00FF00 to #00FFFF)
        range_start = safe_score
        range_end = ((max_score-safe_score) / 2) + safe_score
        true_range = range_end - range_start
        a = 255 * ((score - range_start) / true_range) # value between 0 and 256
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#00FF" + (hex(a)[-1]) + (hex(b)[-1])

    elif score < max_score: # turquoise to blue (#00FFFF to #0000FF)
        range_start = ((max_score-safe_score) / 2) + safe_score
        range_end = max_score
        true_range = range_end - range_start
        a = 255 * (1 - (score - range_start) / true_range) # value between 0 and 256
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#00" + (hex(a)[-1]) + (hex(b)[-1]) + "FF"

    else: # blue for scores equal to or greater then max score
        color = "#0000FF"

    return color

# a safe level of ozone isn't something I've been able to determine exactly. but the agreed upon normal in dobson units (DU) seems to be 300
# https://theozonehole.com/dobsonunit.htm
patch_holes = True

for k in points:
    p = points[k]
    for i in range(len(p['points'])):
        point = p['points'][i]
        score = point['score']

        if score == 0 and patch_holes:
            if i > 0 and i < len(p['points']) - 1:
                if p['points'][i-1] != 0 and p['points'][i+1] != 0:
                    score = (p['points'][i-1]['score'] + p['points'][i+1]['score']) / 2

        point['color'] = score_to_color(score, 300, p['max'])
        point['text'] = str(point['score'])



#p = '20041001'
dates = points.keys()
dates.sort()
for p in dates():
    # define the world map
    world_map = folium.Map(width=500, height=500, location=[0, 0], zoom_start=1)

    # bounds parameter: bounds (list of points (latitude, longitude)) - Latitude and Longitude of line (Northing, Easting)
    for point in points[p]['points']:
        upper_left  = (point['Latitude']+points[p]['lat_step']/2, point['Longitude']-points[p]['long_step']/2)
        upper_right = (point['Latitude']+points[p]['lat_step']/2, point['Longitude']+points[p]['long_step']/2)
        lower_right = (point['Latitude']-points[p]['lat_step']/2, point['Longitude']-points[p]['long_step']/2)
        lower_left  = (point['Latitude']-points[p]['lat_step']/2, point['Longitude']+points[p]['long_step']/2)
        folium.Rectangle(
            bounds=[upper_left, upper_right, lower_right, lower_left],
            fill=True,
            fill_color=point['color'],
            color=point['color'],
            opacity=0.1,
            popup=point['text'],
        ).add_to(world_map)

    img_data = world_map._to_png()

    img = Image.open(io.BytesIO(img_data))
    img.crop((0, 0, 500, 500)).save(p + '.png')
