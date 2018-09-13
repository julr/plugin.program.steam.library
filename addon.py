# -*- coding: utf-8 -*-

import sys
import os
import glob
import re
import urllib
import urlparse
import xml.etree.ElementTree as ET
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc


# some "global" variables
base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
args = urlparse.parse_qs(sys.argv[2][1:])
mode = args.get('mode', [None])[0]

addon = xbmcaddon.Addon()
addon_folder = addon.getAddonInfo('path')
library_folder = addon_folder + '/library'
games_images_folder = library_folder + '/images'
games_xml = library_folder + '/games.xml'

blacklisted_ids = ('228980')  # Steamworks Common Redistributables (not a game)


# functions
def build_url(query):
    return base_url + '?' + urllib.urlencode(query)


def to_percent(current_element, num_elements):
    percent_float = 100.0 * (float(current_element)/float(num_elements))
    return 100 if percent_float > 100.0 else int(round(percent_float, 0))


def write_games_xml(games):
    if os.path.isfile(games_xml):
        os.remove(games_xml)

    tree = ET.Element('games')
    for game in games:
        game_entry = ET.SubElement(tree, 'game')
        name_entry = ET.SubElement(game_entry, 'name')
        name_entry.text = game[0].decode('utf-8')
        id_entry = ET.SubElement(game_entry, 'appid')
        id_entry.text = game[1]
    ET.ElementTree(tree).write(games_xml, encoding='UTF-8',
                               xml_declaration=True)


def read_games_xml():
    games = []
    if os.path.isfile(games_xml):
        tree = ET.parse(games_xml)
        root = tree.getroot()
        for game in root.findall('game'):
            name = game.find('name').text
            appid = game.find('appid').text
            games.append((name, appid))

    games.sort()
    return games


def get_installed_games(path, progress_dialog=None):
    games = []

    # check if the path is a steam library path ("libraryfolders.vdf" exists)
    if os.path.isfile(path + '/steamapps/libraryfolders.vdf'):
        app_regex = re.compile('"appid"\s+"(\d+)"')
        name_regex = re.compile('"name"\s+"(.+?)"')

        acf_files = glob.glob(path + '/steamapps/*.acf')
        num_files = len(acf_files)
        for i in range(num_files):
            if progress_dialog:
                progress_dialog.update(to_percent(i+1, num_files))
            with open(acf_files[i], 'r') as f:
                data = f.read()
            # extract name and id from acf file
            id_match = app_regex.search(data)
            name_match = name_regex.search(data)
            # check if the name and appid found
            if id_match and name_match:
                # blacklisted?
                if id_match.group(1) not in blacklisted_ids:
                    games.append((name_match.group(1), id_match.group(1)))
            else:
                xbmc.log('Steam Library: Unable to parse: %s' % acf_files[i],
                         level=xbmc.LOGNOTICE)
    else:
        xbmc.executebuiltin('Notification(Steam Library,'
                            'Not a valid Steam path: %s)' % path)

    games.sort()
    return games


def download_game_images(games, progress_dialog=None):
    if not os.path.isdir(games_images_folder):
        os.mkdir(games_images_folder)
    num_games = len(games)
    for i in range(num_games):
        image_path = '%s/%s.jpg' % (games_images_folder, games[i][1])
        if progress_dialog:
            progress_dialog.update(to_percent(i+1, num_games))
        if not os.path.isfile(image_path):
            fn, h = urllib.urlretrieve('https://steamcdn-a.akamaihd.net/steam/'
                                       'apps/%s/header.jpg' % games[i][1],
                                       image_path)
            # not an image file (redirected, 404 etc...)
            if h.getheader('content-type') != 'image/jpeg':
                os.remove(image_path)


# add-on entry
if mode is None:
    games = read_games_xml()
    if addon.getSetting('launch_steam_entry') == 'true':
        url = build_url({'mode': 'launch', 'command': 'open',
                        'parameter': 'bigpicture'})
        li = xbmcgui.ListItem('Launch Steam', iconImage=addon_folder +
                              '/resources/steam_logo.png')
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)

    for game in games:
        url = build_url({'mode': 'launch', 'command': 'rungameid',
                        'parameter': game[1]})
        image_path = '%s/%s.jpg' % (games_images_folder, game[1])
        if not os.path.isfile(image_path):
            image_path = addon_folder + '/resources/no_image.png'
        li = xbmcgui.ListItem(game[0], iconImage=image_path)
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)

    xbmcplugin.endOfDirectory(addon_handle)

elif mode == 'launch':
    command = args['command'][0]
    parameter = args['parameter'][0]
    os.startfile('steam://%s/%s' % (command, parameter))

elif mode == 'scan':
    if not os.path.isdir(library_folder):
        os.mkdir(library_folder)
    dialog_scan = xbmcgui.DialogProgressBG()
    dialog_scan.create('Scanning library', 'Steam Library')
    games = get_installed_games(addon.getSetting('steam_folder'), dialog_scan)
    dialog_scan.close()
    if addon.getSetting('download_images') == 'true':
        dialog_download = xbmcgui.DialogProgressBG()
        dialog_download.create('Downloading images', 'Steam Library')
        download_game_images(games, dialog_download)
        dialog_download.close()
    write_games_xml(games)
    xbmc.executebuiltin('Notification(Steam Library,Found %i games)'
                        % len(games))

else:
    xbmc.log('Steam Library: unkown mode called: %s'
             % mode, level=xbmc.LOGNOTICE)
