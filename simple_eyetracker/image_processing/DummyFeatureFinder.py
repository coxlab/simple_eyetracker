



class DummyEyeFeatureFinder(object):

    def __init__(self):
        self.features = {}

    # analyze the image and return dictionary of features gleaned
    # from it
    def analyze_image(self, im, guess=None, **kwargs):
        self.features = {'im_array': im}
        return

    def get_result(self):
        return self.features
    
  
