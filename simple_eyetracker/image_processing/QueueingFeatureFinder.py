#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  CompositeEyeFeatureFinder.py
#  EyeTrackerStageDriver
#
#  Created by Davide Zoccolan on 9/10/08.
#  Copyright (c) 2008 __MyCompanyName__. All rights reserved.
#

from EyeFeatureFinder import *
from scipy import *
from numpy import *

from threading import Thread
from Queue import Queue

import time



class FFWorker(Thread):
    """ Thread executing tasks from a given tasks queue """
    def __init__(self, input_queue, output_queue, ff):
        Thread.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.feature_finder = ff
        self.daemon = True
        self.start()

    def run(self):
        while True:
            im = self.input_queue.get()
            try:
                self.feature_finder.analyze_image(im)
                result = self.feature_finder.get_result()
                self.output_queue.put(result)
            except Exception as e:
                # An exception happened in this thread
                print(e)
            

class FFThreadPool:
    """ Pool of threads consuming tasks from a queue """
    def __init__(self, num_threads, ff_creator):
        self.input_queue = Queue(num_threads)
        self.output_queue = Queue(num_threads)
        for i in range(0, num_threads):
            FFWorker(self.input_queue, self.output_queue, ff_creator())

    def process_image(self, im):
        """ Add a task to the queue """
        self.input_queue.put(im)

    def get_result(self):
        return self.output_queue.get()

    def wait_completion(self):
        """ Wait for completion of all the tasks in the queue """
        self.tasks.join()


class QueueingFeatureFinder(EyeFeatureFinder):

    # ==================================== function: __init__ ========================================
    def __init__(self, ff_creator, nworkers=8):

        self.worker_pool = FFThreadPool(nworkers, ff_creator)


    # ==================================== function: analyzeImage ========================================

    def analyze_image(self, im, guess={}, **kwargs):
        self.worker_pool.process_image(im)

    def get_result(self):
        return self.worker_pool.get_result()
