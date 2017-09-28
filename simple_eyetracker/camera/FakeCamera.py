#
#  SimulatedCameraDevice.py
#  EyeTrackerStageDriver
#
#  Created by David Cox on 5/26/08.
#  Copyright (c) 2008 __MyCompanyName__. All rights reserved.
#


import numpy as np
import os
import cPickle as pickle
import PIL.Image as Image
import time
import imageio

import threading
from Queue import Queue


def load_image(fn):
    ext = os.path.splitext(fn)[1].lower()
    if ext in ('.jpg', '.png'):
        im = Image.open(fn)
        im_array = array(im).astype(float)
        if(im_array.ndim == 3):
            im_array = mean(im_array[:,:,:3], 2)
    elif ext == '.pkl':
        im_array = pickle.load(open(fn)).astype(float)

    return im_array


def make_file_iter(d, exts=('.jpg', '.png', '.pkl')):
    while True:  # this is an infinite iterator
        for r, sd, fs in os.walk(d):
            for fn in fs:
                ext = os.path.splitext(fn)[1].lower()
                if ext in exts:
                    yield load_image(os.path.join(r, fn))

def make_video_iter(fn):
    vid = imageio.get_reader(fn, 'ffmpeg')
    l = vid.get_length() - 5
    i = -1
    while True:  # this is an infinite iterator
        i += 1
        i %= l
        yield vid.get_data(i)


class FakeCamera:
    
    def __init__(self, filename):
        
        self.filename = filename
        self.im_array = None
        self.width = 0
        self.height = 0

        self.frame_number = 0

        self.camera = None
        
        if(self.filename is not None):
            ext = os.path.splitext(self.filename)[1].lower()

            if (os.path.isdir(self.filename)):
                self.image_iter = make_file_iter(self.filename)
                self.im_array = self.image_iter.next()
            elif ext in ('.avi', '.m4v'):
                self.image_iter = make_video_iter(self.filename)
                self.im_array = self.image_iter.next()
            else:
                self.im_array = load_image(self.filename)
        else:
            self.im_array = None
        
        if self.im_array is not None:
            (self.width, self.height, _) = self.im_array.shape

        self.wait = 0.0

    @property
    def roi_width(self):
        return self.width

    @roi_width.setter
    def roi_width(self, value):
        self.width = int(value)

    @property
    def roi_height(self):
        return self.height

    @roi_height.setter
    def roi_height(self, value):
        self.height = int(value)



    def acquire_image(self):
        if hasattr(self, 'image_iter'):
            self.im_array = self.image_iter.next()
            self.im_array = np.mean(self.im_array, 2)
        
        time.sleep(self.wait)
       
        self.frame_number += 1

        return self.im_array[0:self.width, 0:self.height], {'frame_number': self.frame_number, 'timestamp': time.time()}

    def shutdown(self):
        return


