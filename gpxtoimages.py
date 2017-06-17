# -*- coding: utf-8 -*-
import sys, os
import subprocess
import datetime, time
import argparse
import cairo
import math

gpxfile = None
output = None

parser = argparse.ArgumentParser()
parser.add_argument("-g", "--gpx", dest="gpxfile",
                  help="the input GPX file to convert into images",
                  required=True)
parser.add_argument("-o", "--output",
                  dest="outputfolder", default='./images',
                  help="the ouput folder, images will be created inside")

args = parser.parse_args()

##conversion du fichier GPX
p = subprocess.Popen(['gpsbabel', '-t', '-i', 'gpx', '-f', args.gpxfile, '-o', 'unicsv', '-x', 'track,course,speed', '-F', '/dev/stdout'], 
    stdout=subprocess.PIPE, 
    stderr=subprocess.PIPE)
out, err = p.communicate()
out = out.split('\n')
out = out[1:] ##la première ligne est l'entête (No,Latitude,Longitude,Altitude,Speed,Course,Date,Time)


##on récupère la vitesse à chaque seconde
##le GPS n'enregistre pas toute les secondes, il faut donc compléter les vides en calculant la moyenne
datas = [] #(datetime, speed, lat, lon)
average_speed = 0
track_length = 0
total_time = 0


t1 = None
t2 = None
v1 = None
v2 = None
lat1 = None
lat2 = None
lon1 = None
lon2 = None
elevation1 = None
elevation2 = None
vmax = None
vmin = None
tmin = None
tmax = None
latmin = None
latmax = None
lonmin = None
lonmax = None
elevationmin = None
elevationmax = None

for line in out:
    line = line.replace('\n', '').replace('\r', '')
    split = line.split(',')
    if not len(split) == 8:
        continue

    speed = float(split[4]) * 3.6 ##conversion de la vitesse en km/h
    t = datetime.datetime.strptime('%s %s' % (split[6], split[7]) , "%Y/%m/%d %H:%M:%S")
    lat = float(split[1])
    lon = float(split[2])
    elevation = float(split[3])

    if not vmax or vmax < speed:
        vmax = speed
    if not vmin or vmin > speed:
        vmin = speed

    if not tmax or tmax < t:
        tmax = t
    if not tmin or tmin > t:
        tmin = t

    if not latmax or latmax < lat:
        latmax = lat
    if not latmin or latmin > lat:
        latmin = lat

    if not lonmax or lonmax < lon:
        lonmax = lon
    if not lonmin or lonmin > lon:
        lonmin = lon

    if not elevationmax or elevationmax < elevation:
        elevationmax = elevation
    if not elevationmin or elevationmin > elevation:
        elevationmin = elevation


    if not t1:
        t1 = t
        v1 = speed
        lon1 = lon
        lat1 = lat
        elevation1 = elevation
        datas.append( {'datetime': t, 'speed': speed, 'lon': lon, 'lat': lat, 'elevation': elevation } )
    else:
        t2 = t
        v2 = speed
        lon2 = lon
        lat2 = lat
        elevation2 = elevation

        ##on complète les secondes manquantes
        start = int(time.mktime(t1.timetuple())) + 1
        for i in range(start, int(time.mktime(t2.timetuple()))):
            _t = t1 + datetime.timedelta(seconds=i-start+1)
            _v = (v1 + v2) / 2.
            _lat = (lat1 + lat2) / 2.
            _lon = (lon1 + lon2) / 2.
            _elevation = (elevation1 + elevation2) / 2.
            datas.append( {'datetime': _t, 'speed': _v, 'lon': _lon, 'lat': _lat, 'elevation': _elevation} ) ##ici on pourrait faire une moyenne pondérer, si il manque beaucoup de secondes la moyenne simple n'est pas très précise

        datas.append({'datetime': t, 'speed': speed, 'lon': lon, 'lat': lat, 'elevation': elevation})
        t1 = t2
        t2 = None
        v1 = v2
        v2 = None
        lon1 = lon2
        lon2 = None
        lat1 = lat2
        lat2 = None
        elevation1 = elevation2
        elevation2 = None


total_time = datas[len(datas)-1]['datetime'] - datas[0]['datetime']

##on modifie l'elevation max pour avoir un multiple de 500.
elevationmax = int(elevationmax + 1)
while elevationmax % 100 > 0:
    elevationmax += 1

##calcul du dénivelé positif et négatif
elevationgain = 0
elevationloss = 0
elevation_prev = None
for item in datas:
    if not elevation_prev:
        elevation_prev = item['elevation']
    else:
        if elevation_prev < item['elevation']:
            elevationgain += item['elevation'] - elevation_prev
        else:
            elevationloss += elevation_prev - item['elevation']

        elevation_prev = item['elevation']



WIDTH = 800
HEIGHT = 260

def calc_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    km = 6371 * c
    return km


TRACK_OFFSET_X = 10
TRACK_OFFSET_Y = 10
TRACK_WIDTH = 190
TRACK_HEIGHT = 190
##initialisation des valeurs pour dessiner le tracé du cricuit
##on prend la plus plus grande distance la longitude et la latitude
latdiff = calc_distance(latmin, lonmin, latmax, lonmin)
londiff = calc_distance(latmin, lonmin, latmin, lonmax)
maxdiff = latdiff
if londiff > latdiff:
    maxdiff = londiff
##on calcul le coef de mise à l'échelle coordonnées GPS -> pixels écran
scale = TRACK_WIDTH / maxdiff
##on calcul la nouvelle hauteur de la zone carte
#parce qu'il est nécessaire de remonter la carte, par défaut elle se dessine sur le bas de la zone
dist = calc_distance(latmin, lonmin, latmax, lonmin)
TRACK_HEIGHT = dist * scale
def build_track(item, ctx):

    x_start = None
    y_start = None

    ctx.set_source_rgba(1, 1, 1, 0.8)
    ctx.rectangle (TRACK_OFFSET_X - 5, TRACK_OFFSET_Y - 5, TRACK_WIDTH + 10, TRACK_HEIGHT + 10)
    ctx.fill()

    for data in datas:
        dist = calc_distance(latmin, lonmin, data['lat'], lonmin)
        y = TRACK_HEIGHT - (dist * scale) + TRACK_OFFSET_Y

        dist = calc_distance(latmin, lonmin, latmin, data['lon'])
        x = dist * scale + TRACK_OFFSET_X

        if x_start:
            ctx.set_source_rgb(data['speed_color'][0] / 255., data['speed_color'][1] / 255., data['speed_color'][2] / 255.)
            ctx.set_line_width(4)
            ctx.move_to(x_start, y_start)
            ctx.line_to(x, y) 
            ctx.stroke()
            ctx.fill()

        x_start = x
        y_start = y

    ##on dessine le point courant
    dist = calc_distance(latmin, lonmin, item['lat'], lonmin)
    y = TRACK_HEIGHT - (dist * scale) + TRACK_OFFSET_Y

    dist = calc_distance(latmin, lonmin, latmin, item['lon'])
    x = dist * scale + TRACK_OFFSET_X

    ctx.set_source_rgb(0/255., 0/255., 255/255.)
    ctx.arc(x, y, 5, 0.0, 2.0 * math.pi)
    ctx.fill()


INFO_OFFSET_X = 210
INFO_OFFSET_Y = 10
INFO_WIDTH = 150
INFO_HEIGHT = 90
if INFO_HEIGHT < TRACK_HEIGHT:
    INFO_HEIGHT = TRACK_HEIGHT
def build_info(item, ctx):
    ctx.set_source_rgba(1, 1, 1, 0.8)
    ctx.rectangle (INFO_OFFSET_X, INFO_OFFSET_Y - 5, INFO_WIDTH, INFO_HEIGHT + 10)
    ctx.fill()

    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.select_font_face("Sans",
            cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(20)
    text = '%0.2f km' % track_length
    x_bearing, y_bearing, width, height = ctx.text_extents(text)[:4]
    ctx.move_to(INFO_OFFSET_X + 5, INFO_OFFSET_Y + 5 + height)
    ctx.show_text(text)

    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.select_font_face("Sans",
            cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(20)
    text = '%0.2f km/h' % average_speed
    x_bearing, y_bearing, width, height2 = ctx.text_extents(text)[:4]
    ctx.move_to(INFO_OFFSET_X + 5, INFO_OFFSET_Y + 5 + 15 + height + height2)
    ctx.show_text(text)

    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.select_font_face("Sans",
            cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(20)
    text = '%0.0f m d+' % elevationgain
    x_bearing, y_bearing, width, height3 = ctx.text_extents(text)[:4]
    ctx.move_to(INFO_OFFSET_X + 5, INFO_OFFSET_Y + 5 + 15 + 15 + height + height2 + height3)
    ctx.show_text(text)


SPEED_OFFSET_X = INFO_OFFSET_X + INFO_WIDTH + 15
SPEED_OFFSET_Y = 10
SPEED_WIDTH = 360
SPEED_HEIGHT = 60
def build_speed(item, ctx):
    ctx.set_source_rgba(0, 0, 0, 0.3)
    ctx.rectangle (SPEED_OFFSET_X, SPEED_OFFSET_Y, SPEED_WIDTH, SPEED_HEIGHT)
    ctx.fill()

    ctx.set_source_rgb(item['speed_color'][0] / 255., item['speed_color'][1] / 255., item['speed_color'][2] / 255.)
    ctx.rectangle (SPEED_OFFSET_X, SPEED_OFFSET_Y, int(SPEED_WIDTH * (item['speed']/vmax)), SPEED_HEIGHT)
    ctx.fill()

    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.select_font_face("Sans",
            cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(50)
    text = '%0.1f km/h' % item['speed']
    x_bearing, y_bearing, width, height = ctx.text_extents(text)[:4]
    ctx.move_to(SPEED_OFFSET_X + SPEED_WIDTH / 2 - width/2, SPEED_OFFSET_Y + SPEED_HEIGHT / 2 + height/2)
    ctx.show_text(text)


ELEVATION_OFFSET_X = 10
ELEVATION_OFFSET_Y = TRACK_HEIGHT + TRACK_OFFSET_X + 15
ELEVATION_WIDTH = TRACK_WIDTH
ELEVATION_HEIGHT = 60
def build_elevation(item, ctx):
    ctx.set_source_rgba(1, 1, 1, 0.8)
    ctx.rectangle (ELEVATION_OFFSET_X-5, ELEVATION_OFFSET_Y-5, ELEVATION_WIDTH+10, ELEVATION_HEIGHT+10)
    ctx.fill()

    #on doit afficher total_time.total_seconds() sur ELEVATION_WIDTH pixels
    ##on calcul le coef de mise à l'echelle, puis pour chaque pixel on affiche le dénivelé au temps correspondant
    scale_x = total_time.total_seconds() / float(ELEVATION_WIDTH)

    for px in range(0, ELEVATION_WIDTH):
        d = datas[0]['datetime'] + datetime.timedelta(seconds=int(px*scale_x))

        ##on recherche la données correspondante à cette date
        _item = None
        for i in datas:
            if i['datetime'] == d:
                _item = i
                break

        e = ELEVATION_HEIGHT * (_item['elevation'] - elevationmin) / (elevationmax - elevationmin)

        x = ELEVATION_OFFSET_X + px
        y = ELEVATION_OFFSET_Y + ELEVATION_HEIGHT - e
        y_start = ELEVATION_OFFSET_Y + ELEVATION_HEIGHT

        ctx.set_source_rgba(0, 0, 0, 0.8)
        ctx.set_line_width(1)
        ctx.move_to(x, y_start)
        ctx.line_to(x, y) 
        ctx.stroke()
        ctx.fill()
        

    ##affichage du point actuel
    e = ELEVATION_HEIGHT * (item['elevation'] - elevationmin) / (elevationmax - elevationmin)
    x = ELEVATION_OFFSET_X + (item['datetime'] - datas[0]['datetime']).total_seconds() / total_time.total_seconds() * ELEVATION_WIDTH
    y = ELEVATION_OFFSET_Y + ELEVATION_HEIGHT - e

    ctx.set_source_rgb(0/255., 0/255., 255/255.)
    ctx.arc(x, y, 5, 0.0, 2.0 * math.pi)
    ctx.fill()

    ##écriture elevationmax
    ctx.set_source_rgb(0, 0, 0)
    ctx.select_font_face("Sans",
            cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(14)
    text = '%d m' % elevationmax
    x_bearing, y_bearing, width, height = ctx.text_extents(text)[:4]
    ctx.move_to(ELEVATION_OFFSET_X + 2, ELEVATION_OFFSET_Y + height + 2)
    ctx.show_text(text)


        

##on calcul la couleur de chaque vitesse, du bleu au rouge
##la vitesse moyenne et la longueur du circuit
item_prev = None
for item in datas:
    ##calcul de la couleur
    diffs = [
        { 'diff': 0, 'color': (0, 248, 255)},
        { 'diff': 0.2, 'color': (0, 115, 255)},
        { 'diff': 0.4, 'color': (244, 245, 0)},
        { 'diff': 0.6, 'color': (255, 186, 0)},
        { 'diff': 0.8, 'color': (255, 75, 0)},
        { 'diff': 1, 'color': (255, 0, 0)},
    ]
    diff = (item['speed'] - vmin) / (vmax - vmin)
    _diff = 0
    color = (0, 255, 255)
    for i in diffs:
        if math.fabs(diff-i['diff']) < math.fabs(diff-_diff):
            _diff = i['diff']
            color = i['color']

    item['speed_color'] = color

    ##calcul de la longueur
    if item_prev:
        track_length += calc_distance(item_prev['lat'], item_prev['lon'], item['lat'], item['lon'])
    item_prev = item

average_speed = track_length / total_time.total_seconds() * 60 * 60
###


##supressions du dossier images
os.system('mkdir -p %s' % args.outputfolder)
##

i = 0
for item in datas:
    surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context (surface)

    build_speed(item, ctx)
    build_track(item, ctx)
    build_info(item, ctx)
    build_elevation(item, ctx)

    ctx.stroke()
    surface.write_to_png ('%s/%05d.png' % (args.outputfolder, i))

    i += 1

