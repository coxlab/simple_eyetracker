import threading
import logging
import time
from Queue import Queue
import numpy as np
from simple_eyetracker.util import do_profile
from simple_eyetracker.camera import BaslerCamera, POVRaySimulatedCamera, FakeCamera
from simple_eyetracker.image_processing import (SubpixelStarburstEyeFeatureFinder, 
                                                FastRadialFeatureFinder,
                                                CompositeEyeFeatureFinder,
                                                FrugalCompositeEyeFeatureFinder,
                                                CLSubpixelStarburstEyeFeatureFinder,
                                                PipelinedFeatureFinder,
                                                DummyEyeFeatureFinder,
                                                OpenCLBackend)

class EyeTrackerController(object):

    def __init__(self, settings):

        # store a copy of the settings
        self.settings = settings

        # -------------------------------------------------------------------
        # Output variables
        # 
        # These will be computed by the controller and then accessed by a 
        # GUI object via a getter/setter binding scheme
        # -------------------------------------------------------------------
        self.gaze_azimuth = 0.0
        self.gaze_elevation = 0.0
        self.pupil_position_x = 0.0
        self.pupil_position_y = 0.0
        self.pupil_radius = 0.0
        self.cr_position_x = 0.0
        self.cr_position_y = 0.0

        # how often to send to the UI queue
        self.ui_interval = 0.05

        # -------------------------------------------------------------------
        # Setup camera
        # -------------------------------------------------------------------

        self.camera = None

        use_image = settings.get('use_image_for_camera', False)
        use_povray = settings.get('use_simulated_camera', False)

        if not use_image and not use_povray:
            # use the Basler camera
            try:
                self.camera = BaslerCamera()
                print self.camera
                use_povray = False
                use_image = False
            except Exception as e:
                print(e)
                use_povray = True  # fail over to the simulated camera

        # if use_povray:
        #     self.camera = POVRaySimulatedCamera()
        if use_image:
            im_fn = settings.get('test_image', '/tmp/rat_eye.jpg')
            self.camera = FakeCamera(im_fn)
        


        # -------------------------------------------------------------------
        # Setup image processing
        # -------------------------------------------------------------------
        
        # A "feature finder" is an object designed to find relevant eye features
        # (e.g. pupil center, corneal reflex, etc.)

        # the "overall" feature finder
        self.feature_finder = None

        # the radial feature finder does a fast radial symmetry transform to find
        # a rough center seed for the pupil and cr
        self.radial_ff = None

        # the starburst feature finder takes the seed and refines it by sending out
        # "startburst" rays to find edges of the pupil and cr
        self.starburst_ff = None

        # We have the option to run image processing in multiple processes
        # a setting of "0" says to run everything in one process
        nworkers = settings.get('n_image_processing_workers', 0)

        # todo: choose a Backend here to use

        # Run image processing workers in multiple processes
        if nworkers != 0:

            self.feature_finder = PipelinedFeatureFinder(nworkers)
            workers = self.feature_finder.workers

            self.rffs = []
            self.sbffs = []
            for worker in workers:

                fr_ff = worker.FastRadialFeatureFinder()  # in worker process
                sb_ff = worker.StarBurstEyeFeatureFinder()  # in worker process

                self.rffs.append(fr_ff)
                self.sbffs.append(sb_ff)

                comp_ff = worker.FrugalCompositeEyeFeatureFinder(fr_ff, sb_ff)

                worker.set_main_feature_finder(comp_ff)  # create in worker process

            # self.radial_ff = ParamExpose(self.rffs, rff_params)
            # self.starburst_ff = ParamExpose(self.sbffs, sbff_params)
            self.feature_finder.start()  # start the worker loops
        else:

            # run everything in one process
            b = OpenCLBackend()
            sb_ff = CLSubpixelStarburstEyeFeatureFinder(backend=b)
            fr_ff = FastRadialFeatureFinder(backend=b)

            # comp_ff = FrugalCompositeEyeFeatureFinder(fr_ff, sb_ff)
            comp_ff = CompositeEyeFeatureFinder(fr_ff, sb_ff)

            self.radial_ff = fr_ff
            self.starburst_ff = sb_ff

            self.feature_finder = comp_ff
            # self.feature_finder = DummyEyeFeatureFinder()


        # -------------------------------------------------------------------
        # Set up a calibrator
        # -------------------------------------------------------------------
        self.calibrator = None


        # -------------------------------------------------------------------
        # UI-related
        # -------------------------------------------------------------------
        
        self.canvas_update_timer = None
        self.ui_queue = Queue(2)

        # -------------------------------------------------------------------
        # Start the imaging thread
        # -------------------------------------------------------------------

        # capture one frame as a test
        im, meta = self.camera.acquire_image()

        self.start_continuous_acquisition()



    def start_continuous_acquisition(self):
        logging.info('Starting continuous acquisition')
        self.continuously_acquiring = True

        t = lambda: self.continuously_acquire_images()
        self.acq_thread = threading.Thread(target=t)
        self.acq_thread.start()

    def stop_continuous_acquisition(self):
        logging.debug('Stopping continuous acquisition')
        self.continuously_acquiring = False
        logging.debug("Joining... %s" % self.acq_thread.join())
        logging.debug('Stopped')


    def continuously_acquire_images(self):
        ''' Continuously acquire images in a loop.
            Images are analyzed and then pushed into a queue so that the
            the UI can visualize them
        '''

        logging.info('Started continuously acquiring')

        frame_rate = -1.
        frame_number = 0
        tic = time.time()
        features = None
        gaze_azimuth = 0.0
        gaze_elevation = 0.0
        calibration_status = 0

        features = {}

        last_ui_put_time = time.time()
        
        check_interval = self.settings.get('fps_interval', 10)
        
        self.features = None

        while self.continuously_acquiring:
            self.camera_locked = True


            im, meta = self.camera.acquire_image()
            self.feature_finder.analyze_image(im.astype(np.float32), guess=self.features)
            features = self.feature_finder.get_result()
            self.features = features

            if meta is not None and 'frame_number' in meta:
                frame_number = meta['frame_number']

            # compute frame rate periodically
            if frame_number % check_interval == 0:

                toc = time.time() - tic
                frame_rate = check_interval / toc
                print('Real frame rate: %f' % (check_interval / toc))

                tic = time.time()

            # check if something is wrong
            if features is None:
                logging.error('No features found... sleeping')
                time.sleep(0.004)
                continue

            if 'pupil_position' in features and features['pupil_position'] is not None and features['cr_position'] is not None:

                # timestamp = features.get('timestamp', 0)

                pupil_position = features['pupil_position']
                cr_position = features['cr_position']

                pupil_radius = 0.0
                
                # get pupil radius in mm
                if 'pupil_radius' in features and features['pupil_radius'] \
                    is not None and self.calibrator is not None:

                    if self.calibrator.pixels_per_mm is not None:
                        pupil_radius = features['pupil_radius'] \
                            / self.calibrator.pixels_per_mm
                    else:
                        pupil_radius = -1 * features['pupil_radius']

                if self.calibrator is not None:

                    if not self.pupil_only:

                        (gaze_elevation, gaze_azimuth,
                         calibration_status) = \
                            self.calibrator.transform(pupil_position,
                                cr_position)
                    else:

                        (gaze_elevation, gaze_azimuth,
                         calibration_status) = \
                            self.calibrator.transform(pupil_position, None)


                # set values for the bindings GUI
                if frame_number % check_interval == 0:

                    self.pupil_position_x = pupil_position[1]
                    self.pupil_position_y = pupil_position[0]
                    self.pupil_radius = pupil_radius
                    self.cr_position_x = cr_position[1]
                    self.cr_position_y = cr_position[0]
                    self.gaze_azimuth = gaze_azimuth
                    self.gaze_elevation = gaze_elevation
                    self.calibration_status = calibration_status
                    self.frame_rate = frame_rate


            if (time.time() - last_ui_put_time) > self.ui_interval:
                try:
                    self.ui_queue.put_nowait(features)
                    last_ui_put_time = time.time()
                except:
                    pass

        self.camera_locked = False

        logging.info('Stopped continuous acquiring')
        return

