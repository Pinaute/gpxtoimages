# -*- coding: utf-8 -*-
import sys, os
import subprocess
import datetime, time
import argparse
import cairo
from math import pi, radians, sin, cos, asin, sqrt
from multiprocessing import Process, Queue

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
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

#################TRACK##################
MODULE_DIMENSION_TRACK = 225
TRACK_OFFSET_X = MODULE_DIMENSION_TRACK/2
TRACK_OFFSET_Y = MODULE_DIMENSION_TRACK/2
radius = MODULE_DIMENSION_TRACK/2
##initialisation des valeurs pour dessiner le tracé du circuit
##on prend la plus plus grande distance la longitude et la latitude
latdiff = calc_distance(latmin, lonmin, latmax, lonmin)
londiff = calc_distance(latmin, lonmin, latmin, lonmax)
maxdiff = latdiff
if londiff > latdiff:
    maxdiff = londiff
##on calcul le coef de mise à l'échelle coordonnées GPS -> pixels écran
scale = radius*1.2 / maxdiff
##on calcul la nouvelle hauteur de la zone carte
#parce qu'il est nécessaire de remonter la carte, par défaut elle se dessine sur le bas de la zone
dist = calc_distance(latmin, lonmin, latmax, lonmin)
trackHeight = dist * scale
def build_track(item, ctx):

    x_start = None
    y_start = None

    # Background
    ctx.set_source_rgba(0, 0, 0, 0.3)
    ctx.arc (TRACK_OFFSET_X, TRACK_OFFSET_Y, radius, 0, 2*pi)  
    ctx.fill()
    
    # Border
    ctx.set_line_width(2)
    ctx.set_source_rgb(1,1,1)
    ctx.arc (TRACK_OFFSET_X, TRACK_OFFSET_Y, radius, 0, 2*pi)  
    ctx.stroke()
    
    for data in datas:
        dist = calc_distance(latmin, lonmin, data['lat'], lonmin)
        y = trackHeight - (dist * scale) + MODULE_DIMENSION_TRACK/4

        dist = calc_distance(latmin, lonmin, latmin, data['lon'])
        x = dist * scale + MODULE_DIMENSION_TRACK/4
        
        if x_start:
            ctx.set_source_rgb(data['speed_color'][0] / 255., data['speed_color'][1] / 255., data['speed_color'][2] / 255.)
            ctx.set_line_width(3)
            ctx.move_to(x_start, y_start)
            ctx.line_to(x, y) 
            ctx.stroke()
            ctx.fill()

        x_start = x
        y_start = y

    ##on dessine le point courant
    dist = calc_distance(latmin, lonmin, item['lat'], lonmin)
    y = trackHeight - (dist * scale) + MODULE_DIMENSION_TRACK/4

    dist = calc_distance(latmin, lonmin, latmin, item['lon'])
    x = dist * scale + MODULE_DIMENSION/4

    ctx.set_source_rgb(0/255., 0/255., 255/255.)
    ctx.arc(x, y, 5, 0.0, 2.0 * pi)
    ctx.fill()
    
#################INFO##################
MODULE_DIMENSION = 225
INFO_OFFSET_X = 210
INFO_OFFSET_Y = 10
INFO_WIDTH = 150
INFO_HEIGHT = 90
if INFO_HEIGHT < MODULE_DIMENSION:
    INFO_HEIGHT = MODULE_DIMENSION
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

#################SPEED##################
MODULE_DIMENSION_SPEED = 225
SPEED_OFFSET_X = MODULE_DIMENSION_SPEED/2
SPEED_OFFSET_Y = MODULE_DIMENSION_SPEED/2
def build_speed(item, ctx):
    
    sppedWidht = int(269 * (item['speed']/vmax))+100  #(0 à 259) soit 260 valeurs, et +100 car angle2 min = 100 et max 360
          
    angle2 = sppedWidht * (pi/180.0)
    angle1 = (180 - sppedWidht) * (pi/180.0)
    radius = MODULE_DIMENSION_SPEED/2
   
    ctx.set_source_rgba(0, 0, 0, 0.3)# couleur de fond
    ctx.arc(SPEED_OFFSET_X, SPEED_OFFSET_Y, radius, 0, 2*pi)
    ctx.fill()
    
    ctx.set_line_width(3)
    ctx.set_source_rgb(1,1,1)
    ctx.new_sub_path ()
    ctx.arc(SPEED_OFFSET_X, SPEED_OFFSET_Y, radius, 0, 2*pi)
    ctx.close_path ()
    ctx.stroke()
    
    ctx.new_path()
    ctx.set_source_rgba(item['speed_color'][0] / 255., item['speed_color'][1] / 255., item['speed_color'][2] / 255., 0.7)
    ctx.arc(SPEED_OFFSET_X, SPEED_OFFSET_Y, radius, angle1, angle2)
    ctx.close_path ()
    ctx.fill()

def label1_speed(item, ctx, labelSpeed):  
    ctx.set_source_rgb(1,1,1) 
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(38)
    text = '%0.1f' % item['speed']
    x_bearing, y_bearing, width, height = ctx.text_extents(text)[:4]
    ctx.move_to(SPEED_OFFSET_X-x_bearing-width/2, SPEED_OFFSET_Y-y_bearing-height/2)
    ctx.show_text(text)
    return ctx.text_extents(text)[:4]
    
def label2_speed(item, ctx, labelSpeed):
    tabulation = 10
    ctx.set_source_rgb(1,1,1) 
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL)
    ctx.set_font_size(18)
    text = 'km/h'
    ctx.move_to((SPEED_OFFSET_X-labelSpeed[0]-labelSpeed[2]/2) + labelSpeed[2] + tabulation , SPEED_OFFSET_Y-labelSpeed[1]-labelSpeed[3]/2)
    ctx.show_text(text)

#################ELEVATION##################
MODULE_ELEVATION_WIDTH = 675
MODULE_ELEVATION_HEIGHT = 225
RADIUS = MODULE_ELEVATION_HEIGHT / 10
ELEVATION_OFFSET_X = 20
ELEVATION_OFFSET_Y = 10
ELEVATION_WIDTH = MODULE_ELEVATION_WIDTH - ELEVATION_OFFSET_X*2
ELEVATION_HEIGHT = MODULE_ELEVATION_HEIGHT - ELEVATION_OFFSET_Y*2

def build_elevation(item, ctx):

    # Background
    ctx.set_source_rgba(0, 0, 0, 0.3)
    ctx.new_sub_path ()
    ctx.arc (MODULE_ELEVATION_WIDTH - RADIUS, RADIUS,                           RADIUS, -pi/2, 0      )
    ctx.arc (MODULE_ELEVATION_WIDTH - RADIUS, MODULE_ELEVATION_HEIGHT - RADIUS, RADIUS, 0,     pi/2   )
    ctx.arc (RADIUS,                          MODULE_ELEVATION_HEIGHT - RADIUS, RADIUS, pi/2,  pi     )
    ctx.arc (RADIUS,                          RADIUS,                           RADIUS, pi,    3*pi/2 )
    ctx.close_path ()
    ctx.fill()

    # Border
    ctx.set_line_width(3)
    ctx.set_source_rgb(1,1,1)
    ctx.arc (MODULE_ELEVATION_WIDTH - RADIUS, RADIUS,                           RADIUS, -pi/2, 0      )
    ctx.arc (MODULE_ELEVATION_WIDTH - RADIUS, MODULE_ELEVATION_HEIGHT - RADIUS, RADIUS, 0,     pi/2   )
    ctx.arc (RADIUS,                          MODULE_ELEVATION_HEIGHT - RADIUS, RADIUS, pi/2,  pi     )
    ctx.arc (RADIUS,                          RADIUS,                           RADIUS, pi,    3*pi/2 )
    ctx.close_path ()
    ctx.stroke()

    #on doit afficher total_time.total_seconds() sur MODULE_ELEVATION_WIDTH pixels
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

        ctx.set_source_rgb(1,1,1)
        ctx.set_line_width(3)
        ctx.move_to(x, y_start)
        ctx.line_to(x, y) 
        ctx.stroke()
        ctx.fill()
 
    #affichage du point actuel
    e = ELEVATION_HEIGHT * (item['elevation'] - elevationmin) / (elevationmax - elevationmin)
    x = ELEVATION_OFFSET_X + (item['datetime'] - datas[0]['datetime']).total_seconds() / total_time.total_seconds() * ELEVATION_WIDTH
    y = ELEVATION_OFFSET_Y + ELEVATION_HEIGHT - e
    ctx.set_source_rgb(0/255., 0/255., 255/255.)
    ctx.arc(x, y, 5, 0.0, 2.0 * pi)
    ctx.fill()

    ##écriture elevationmax
    ctx.set_source_rgb(1, 1, 1)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(20)
    text = '%d m' % elevationmax
    x_bearing, y_bearing, width, height = ctx.text_extents(text)[:4]
    ctx.move_to(ELEVATION_OFFSET_X + 2, ELEVATION_OFFSET_Y + height + 2)
    ctx.show_text(text)
        

##on calcul la couleur de chaque vitesse, du bleu au rouge
##la vitesse moyenne et la longueur du circuit
item_prev = None
for item in datas:
    ##calcul de la couleur
    color = []
    for i in range(255,0,-1):
        color.append([0,255,i])
    for i in range(0,255,+1):
        color.append([i,255,0])
    for i in range(255,0,-1):
        color.append([255,i,0])
        
    indexColor = int ((item['speed'] - vmin) / (vmax - vmin) * len(color))
    item['speed_color'] = color[indexColor - 1] 

    ##calcul de la longueur
    if item_prev:
        track_length += calc_distance(item_prev['lat'], item_prev['lon'], item['lat'], item['lon'])
    item_prev = item

average_speed = track_length / total_time.total_seconds() * 60 * 60
###


##supressions du dossier images
os.system('mkdir -p %s' % args.outputfolder)
##
'''
i = 0
for item in datas:
    surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, MODULE_DIMENSION_SPEED, MODULE_DIMENSION_SPEED)
    ctx = cairo.Context (surface)
  
    build_speed(item, ctx)
    labelSpeed = [] 
    labelSpeed = label1_speed(item, ctx, labelSpeed )
    labelSpeed = label2_speed(item, ctx, labelSpeed)
        
    ctx.stroke()
    surface.write_to_png ('%s/%03d-speed.png' % (args.outputfolder, i))

    i += 1

j = 0
for item in datas:
    surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, MODULE_DIMENSION_TRACK, MODULE_DIMENSION_TRACK)
    ctx = cairo.Context (surface)

    build_track(item, ctx)

    ctx.stroke()
    surface.write_to_png ('%s/%03d-track.png' % (args.outputfolder, j))

    j += 1   
'''
k = 0
for item in datas:
    surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, MODULE_ELEVATION_WIDTH, MODULE_ELEVATION_HEIGHT)
    ctx = cairo.Context (surface)

    build_elevation(item, ctx)
    #largeurTexte =  25
    #tabulation = 15
    #espace = 5
    #largeurTexte = build_text1_elevation(item, ctx, largeurTexte ) + largeurTexte + tabulation
    #largeurTexte = build_text2_elevation(item, ctx, largeurTexte)  + largeurTexte + espace
    #largeurTexte = build_text3_elevation(item, ctx, largeurTexte)  + largeurTexte

    ctx.stroke()
    surface.write_to_png ('%s/%03d-elevation.png' % (args.outputfolder, k))

    k += 1
