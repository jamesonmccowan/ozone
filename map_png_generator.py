import numpy as np  # useful for many scientific computing in Python
import pandas as pd # primary data structure library
import folium # !conda install -c conda-forge folium=0.5.0 --yes
import os
import math
import datetime
import time

import io
from PIL import Image
import geckodriver_autoinstaller
geckodriver_autoinstaller.install()


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
        "long_stop":  long_stop,
        "long_step":  long_step,
        "long_bins":  long_bins,

        "lat_start":  lat_start,
        "lat_stop":   lat_stop,
        "lat_step":   lat_step,
        "lat_bins":   lat_bins,
    }


## color the points
# 1. red (#FF0000)
# 2. yellow (#FFFF00)
# 3. green (#00FF00) (safe)
# 4. turquoise (#00FFFF)
# 5. blue (#0000FF)
def score_to_color(score, score_a, score_b, score_c, score_d, score_e):
    color = ""

    if score <= 0: # score should never be 0 or negative, show error state
        color = "#000000"

    elif score <= score_a: # red
        color = "#FF0000"

    elif score < score_b: # red to yellow (#FF0000 to #FFFF00)
        a = 255 * ((score - score_a) / (score_b - score_a)) # value between 0 and 256
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#FF" + (hex(a)[-1]) + (hex(b)[-1]) + "00"

    elif score < score_c: # yellow to green (#FFFF00 to #00FF00)
        a = 255 * (1 - (score - score_b) / (score_c - score_b)) # value between 256 and 0
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#" + (hex(a)[-1]) + (hex(b)[-1]) + "FF00"

    elif score < score_d: # green to turquoise (#00FF00 to #00FFFF)
        a = 255 * ((score - score_c) / (score_d - score_c)) # value between 0 and 256
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#00FF" + (hex(a)[-1]) + (hex(b)[-1])

    elif score < score_e: # turquoise to blue (#00FFFF to #0000FF)
        a = 255 * (1 - (score - score_d) / (score_e - score_d)) # value between 256 and 0
        b = math.floor(a % 16)
        a = math.floor(a / 16)
        color = "#00" + (hex(a)[-1]) + (hex(b)[-1]) + "FF"

    else: # blue for scores equal to or greater then max score
        color = "#0000FF"

    return color


# a safe level of ozone isn't something I've been able to determine exactly. but the agreed upon normal in dobson units (DU) seems to be 300
# https://theozonehole.com/dobsonunit.htm
def color_points(points, patch_holes, score_a, score_b, score_c, score_d, score_e):
    for i in range(len(points)):
            point = points[i]
            score = point['score']

            if score == 0 and patch_holes:
                if i > 0 and i < len(points) - 1:
                    if points[i-1] != 0 and points[i+1] != 0:
                        score = (points[i-1]['score'] + points[i+1]['score']) / 2

            point['color'] = score_to_color(score, score_a, score_b, score_c, score_d, score_e)
            point['text'] = str(point['score'])


def point_to_map(points, name, score_a, score_b, score_c, score_d, score_e):
    # define the world map
    world_map = folium.Map(width=500, height=500, location=[0, 0], zoom_start=1, zoom_control=False, tiles="OpenStreetMap")

    # add text to map
    html = '''
        <div style="">
          <span style="display: inline-block;">
            <span style="background-color: #FF0000;">&#160;{1}&#160;</span><span style="background-color: #FFFF00;">&#160;{2}&#160;</span><span style="background-color: #00FF00;">&#160;{3}&#160;</span><span style="background-color: #00FFFF;">&#160;{4}&#160;</span><span style="background-color: #0000FF;">&#160;{5}&#160;</span>
          </span>
          <span style="display: inline-block; margin-left: 250px;">{0}</span>
        </div>
    '''.format(name, score_a, score_b, score_c, score_d, score_e)
    world_map.get_root().html.add_child(folium.Element(html))

    # bounds parameter: bounds (list of points (latitude, longitude)) - Latitude and Longitude of line (Northing, Easting)
    for point in points['points']:
        upper_left  = (point['Latitude']+points['lat_step']/2, point['Longitude']-points['long_step']/2)
        upper_right = (point['Latitude']+points['lat_step']/2, point['Longitude']+points['long_step']/2)
        lower_right = (point['Latitude']-points['lat_step']/2, point['Longitude']-points['long_step']/2)
        lower_left  = (point['Latitude']-points['lat_step']/2, point['Longitude']+points['long_step']/2)
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
    img.crop((0, 0, 500, 500)).save(name + '.png')


# load the data from the files and export PNG maps of the data
print("ping")
file_list  = sorted(os.listdir('./data/'))
first      = file_list[0][13:21]
last       = file_list[-1][13:21]
start_date = datetime.date(int(first[0:4]), int(first[4:6]), int(first[6:8]))
end_date   = datetime.date(int(last[0:4]), int(last[4:6]), int(last[6:8]))
delta = datetime.timedelta(days=1)
while (start_date <= end_date):
    f = "L3_ozone_omi_{0}.txt".format(start_date.strftime('%Y%m%d'))
    if not os.path.exists(f[13:21] + '.png'):
        if os.path.exists('./data/{0}'.format(f)):
            with open('./data/{0}'.format(f)) as data_file:
                print("opened {0}".format(f))
                raw = data_file.read()
                print("finished loading data, now parsing data")
                data = parse_data(raw)
                print("finished parsing data, now coloring points")
                color_points(data['points'], True, 100, 225, 350, 476, 600)
                print("finished coloring points, now making image")
                point_to_map(data, f[13:21], 100, 225, 350, 476, 600)
                print("image made")
        else:
            print("generating blank image for missing file {0}".format(f))
            data = {
                "points": [{
                    'Latitude':  0,
                    'Longitude': 0,
                    'score': 0,
                    'color': '#ffffff'
                }],
                "max": 300,
                "min": 300,
                "day": f[13:21],

                "long_start": 0,
                "long_stop":  0,
                "long_step":  360,
                "long_bins":  1,

                "lat_start":  0,
                "lat_stop":   0,
                "lat_step":   180,
                "lat_bins":   1,
            }

            color_points(data['points'], True, 100, 225, 350, 476, 600)
            point_to_map(data, f[13:21], 100, 225, 350, 476, 600)
            time.sleep(30) # the map seems to not work if used too fast?
            print("image made")
    else:
        print("skipping image for {0}, already exists".format(f))

    start_date += delta
