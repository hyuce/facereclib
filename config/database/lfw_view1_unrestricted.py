#!/usr/bin/env python

import xbob.db.lfw

# The database to use
name = 'lfw'
db = xbob.db.lfw.Database()
protocol = 'view1'

img_input_dir = '/idiap/resource/database/lfw/all_images'
img_input_ext = '.jpg'

all_files_options = { 'type' : 'unrestricted' }
world_extractor_options = { 'subworld' : 'twofolds', 'type' : 'unrestricted' }
world_projector_options = {'subworld' : 'twofolds', 'type' : 'unrestricted' }
world_enroler_options = { 'subworld' : 'twofolds', 'type' : 'unrestricted' }
features_by_clients_options = { 'subworld' : 'twofolds' }