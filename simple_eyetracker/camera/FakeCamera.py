#
#  SimulatedCameraDevice.py
#  EyeTrackerStageDriver
#
#  Created by David Cox on 5/26/08.
#  Copyright (c) 2008 __MyCompanyName__. All rights reserved.
#


from numpy import *
import os
import cPickle as pickle
import PIL.Image as Image
import time

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
                    yield os.path.join(r, fn)


class FakeCamera:
    
    def __init__(self, filename = None):
        
        self.feature_finder = None
        self.filename = filename
        self.im_array = None
        
        self.frame_number = 0

        self.camera = None
        
        if(self.filename is not None):
            if (os.path.isdir(self.filename)):
                self.file_iter = make_file_iter(self.filename)
            else:
                self.im_array = load_image(self.filename)
        else:
            self.im_array = None
        
        self.wait = 0.0001


    def acquire_image(self):
        if hasattr(self, 'file_iter'):
            self.im_array = load_image(self.file_iter.next())
        
        time.sleep(self.wait)
       
        self.frame_number += 1

        return self.im_array, {'frame_number': self.frame_number, 'timestamp': time.time()}

    def shutdown(self):
        return


