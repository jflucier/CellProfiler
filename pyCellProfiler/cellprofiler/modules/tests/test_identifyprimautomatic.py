__version__ = "$Revision$"
import os

import unittest
import numpy
import scipy.ndimage
import tempfile

import cellprofiler.modules.identifyprimautomatic as ID
from cellprofiler.modules.injectimage import InjectImage
import cellprofiler.variable
import cellprofiler.cpimage
import cellprofiler.objects
import cellprofiler.measurements
import cellprofiler.pipeline
from cellprofiler.matlab.cputils import get_matlab_instance
import cellprofiler.modules.tests

class test_IdentifyPrimAutomatic(unittest.TestCase):
    def test_00_00_init(self):
        x = ID.IdentifyPrimAutomatic()
    
    def test_01_01_image_name(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.IMAGE_NAME_VAR).set_value("MyImage")
        self.assertEqual(x.image_name, "MyImage")
    
    def test_01_02_object_name(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).set_value("MyObject")
        self.assertEqual(x.object_name, "MyObject")
    
    def test_01_03_size_range(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.size_range.min,10)
        self.assertEqual(x.size_range.max,40)
        x.variable(ID.SIZE_RANGE_VAR).set_value("5,100")
        self.assertEqual(x.size_range.min,5)
        self.assertEqual(x.size_range.max,100)
    
    def test_01_04_exclude_size(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.exclude_size.value,"Default should be yes")
        x.variable(ID.EXCLUDE_SIZE_VAR).set_value("No")
        self.assertFalse(x.exclude_size.value)
        x.variable(ID.EXCLUDE_SIZE_VAR).set_value("Yes")
        self.assertTrue(x.exclude_size.value)
        
    def test_01_05_merge_objects(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertFalse(x.merge_objects.value, "Default should be no")
        x.variable(ID.MERGE_CHOICE_VAR).set_value("Yes")
        self.assertTrue(x.merge_objects.value)
        x.variable(ID.MERGE_CHOICE_VAR).set_value("No")
        self.assertFalse(x.merge_objects.value)
    
    def test_01_06_exclude_border_objects(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.exclude_border_objects.value,"Default should be yes")
        x.variable(ID.EXCLUDE_BORDER_OBJECTS_VAR).set_value("Yes")
        self.assertTrue(x.exclude_border_objects.value)
        x.variable(ID.EXCLUDE_BORDER_OBJECTS_VAR).set_value("No")
        self.assertFalse(x.exclude_border_objects.value)
    
    def test_01_07_threshold_method(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.threshold_method, ID.TM_OTSU_GLOBAL, "Default should be Otsu global")
        x.variable(ID.THRESHOLD_METHOD_VAR).set_value(ID.TM_BACKGROUND_GLOBAL)
        self.assertEqual(x.threshold_method, ID.TM_BACKGROUND_GLOBAL)
    
    def test_01_07_01_threshold_modifier(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.threshold_modifier, ID.TM_GLOBAL)
        x.variable(ID.THRESHOLD_METHOD_VAR).set_value(ID.TM_BACKGROUND_ADAPTIVE)
        self.assertEqual(x.threshold_modifier, ID.TM_ADAPTIVE)

    def test_01_07_02_threshold_algorithm(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.threshold_algorithm == ID.TM_OTSU, "Default should be Otsu")
        x.variable(ID.THRESHOLD_METHOD_VAR).set_value(ID.TM_BACKGROUND_GLOBAL)
        self.assertTrue(x.threshold_algorithm == ID.TM_BACKGROUND)

    def test_01_08_threshold_range(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.threshold_range.min,0)
        self.assertEqual(x.threshold_range.max,1)
        x.variable(ID.THRESHOLD_RANGE_VAR).set_value(".2,.8")
        self.assertEqual(x.threshold_range.min,.2)
        self.assertEqual(x.threshold_range.max,.8)
    
    def test_01_09_threshold_correction_factor(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.threshold_correction_factor.value,1)
        x.variable(ID.THRESHOLD_CORRECTION_VAR).set_value("1.5")
        self.assertEqual(x.threshold_correction_factor.value,1.5)
    
    def test_01_10_object_fraction(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.object_fraction.value,'0.01')
        x.variable(ID.OBJECT_FRACTION_VAR).set_value("0.2")
        self.assertEqual(x.object_fraction.value,'0.2')
        
    def test_01_11_unclump_method(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.unclump_method.value, ID.UN_INTENSITY, "Default should be intensity, was %s"%(x.unclump_method))
        x.variable(ID.UNCLUMP_METHOD_VAR).set_value(ID.UN_MANUAL)
        self.assertEqual(x.unclump_method.value, ID.UN_MANUAL)

    def test_01_12_watershed_method(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertEqual(x.watershed_method.value, ID.WA_INTENSITY, "Default should be intensity")
        x.variable(ID.WATERSHED_VAR).set_value(ID.WA_DISTANCE)
        self.assertEqual(x.watershed_method.value, ID.WA_DISTANCE)
        
    def test_01_13_smoothing_filter_size(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.automatic_smoothing.value, "Default should be automatic")
        x.automatic_smoothing.value = False
        x.variable(ID.SMOOTHING_SIZE_VAR).set_value("10")
        self.assertFalse(x.automatic_smoothing.value)
        self.assertEqual(x.smoothing_filter_size,10)
    
    def test_01_14_maxima_suppression_size(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.automatic_suppression.value, "Default should be automatic")
        x.automatic_suppression.value= False
        x.variable(ID.MAXIMA_SUPPRESSION_SIZE_VAR).set_value("10")
        self.assertFalse(x.automatic_suppression.value)
        self.assertEqual(x.maxima_suppression_size.value,10)
        
    def test_01_15_use_low_res(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.low_res_maxima.value)
        x.variable(ID.LOW_RES_MAXIMA_VAR).set_value("No")
        self.assertFalse(x.low_res_maxima.value)
        x.variable(ID.LOW_RES_MAXIMA_VAR).set_value("Yes")
        self.assertTrue(x.low_res_maxima.value)
        
    def test_01_17_fill_holes(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.fill_holes.value)
        x.variable(ID.FILL_HOLES_OPTION_VAR).value = cellprofiler.variable.NO
        self.assertFalse(x.fill_holes.value)
        x.variable(ID.FILL_HOLES_OPTION_VAR).value = cellprofiler.variable.YES
        self.assertTrue(x.fill_holes.value)
        
    def test_01_18_test_mode(self):
        x = ID.IdentifyPrimAutomatic()
        self.assertTrue(x.test_mode.value)
        x.variable(ID.TEST_MODE_VAR).value = cellprofiler.variable.NO
        self.assertFalse(x.test_mode.value)
        x.variable(ID.TEST_MODE_VAR).value = cellprofiler.variable.YES
        self.assertTrue(x.test_mode.value)
        
    def test_02_000_test_zero_objects(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".1,1"
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((25,25))
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented == 0))
        self.assertTrue("Image" in measurements.get_object_names())
        self.assertTrue("my_object" in measurements.get_object_names())
        self.assertTrue("Threshold_FinalThreshold_my_object" in measurements.get_feature_names("Image"))
        self.assertTrue("Count_my_object" in measurements.get_feature_names("Image"))
        count = measurements.get_current_measurement("Image","Count_my_object")
        self.assertEqual(count,0)
        self.assertTrue("Location_Center_X" in measurements.get_feature_names("my_object"))
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),0)
        self.assertTrue("Location_Center_Y" in measurements.get_feature_names("my_object"))
        location_center_y = measurements.get_current_measurement("my_object","Location_Center_Y")
        self.assertTrue(isinstance(location_center_y,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_y.shape),0)

    def test_02_001_test_zero_objects_wa_in_lo_in(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".1,1"
        x.watershed_method.value = ID.WA_INTENSITY
        x.unclump_method.value = ID.UN_INTENSITY
        img = numpy.zeros((25,25))
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented == 0))

    def test_02_002_test_zero_objects_wa_di_lo_in(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".1,1"
        x.watershed_method.value = ID.WA_DISTANCE
        x.unclump_method.value = ID.UN_INTENSITY
        img = numpy.zeros((25,25))
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented == 0))
        
    def test_02_003_test_zero_objects_wa_in_lo_sh(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".1,1"
        x.watershed_method.value = ID.WA_INTENSITY
        x.unclump_method.value = ID.UN_SHAPE
        img = numpy.zeros((25,25))
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented == 0))

    def test_02_004_test_zero_objects_wa_di_lo_sh(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".1,1"
        x.watershed_method.value = ID.WA_DISTANCE
        x.unclump_method.value = ID.UN_SHAPE
        img = numpy.zeros((25,25))
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented == 0))

    def test_02_01_test_one_object(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.SMOOTHING_SIZE_VAR).value = 0
        x.variable(ID.AUTOMATIC_SMOOTHING_VAR).value = False
        x.watershed_method.value = ID.WA_NONE
        img = one_cell_image()
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented[img>0] == 1))
        self.assertTrue(numpy.all(img[segmented==1] > 0))
        self.assertTrue("Image" in measurements.get_object_names())
        self.assertTrue("my_object" in measurements.get_object_names())
        self.assertTrue("Threshold_FinalThreshold_my_object" in measurements.get_feature_names("Image"))
        threshold = measurements.get_current_measurement("Image","Threshold_FinalThreshold_my_object")
        self.assertTrue(threshold < .5)
        self.assertTrue("Count_my_object" in measurements.get_feature_names("Image"))
        count = measurements.get_current_measurement("Image","Count_my_object")
        self.assertEqual(count,1)
        self.assertTrue("Location_Center_X" in measurements.get_feature_names("my_object"))
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),1)
        self.assertTrue(location_center_x[0]>8)
        self.assertTrue(location_center_x[0]<12)
        self.assertTrue("Location_Center_Y" in measurements.get_feature_names("my_object"))
        location_center_y = measurements.get_current_measurement("my_object","Location_Center_Y")
        self.assertTrue(isinstance(location_center_y,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_y.shape),1)
        self.assertTrue(location_center_y[0]>13)
        self.assertTrue(location_center_y[0]<16)

    def test_02_02_test_two_objects(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.watershed_method.value = ID.WA_NONE
        img = two_cell_image()
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        self.assertTrue("Image" in measurements.get_object_names())
        self.assertTrue("my_object" in measurements.get_object_names())
        self.assertTrue("Threshold_FinalThreshold_my_object" in measurements.get_feature_names("Image"))
        threshold = measurements.get_current_measurement("Image","Threshold_FinalThreshold_my_object")
        self.assertTrue(threshold < .6)
        self.assertTrue("Count_my_object" in measurements.get_feature_names("Image"))
        count = measurements.get_current_measurement("Image","Count_my_object")
        self.assertEqual(count,2)
        self.assertTrue("Location_Center_X" in measurements.get_feature_names("my_object"))
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),2)
        self.assertTrue(location_center_x[0]>8)
        self.assertTrue(location_center_x[0]<12)
        self.assertTrue(location_center_x[1]>28)
        self.assertTrue(location_center_x[1]<32)
        self.assertTrue("Location_Center_Y" in measurements.get_feature_names("my_object"))
        location_center_y = measurements.get_current_measurement("my_object","Location_Center_Y")
        self.assertTrue(isinstance(location_center_y,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_y.shape),2)
        self.assertTrue(location_center_y[0]>33)
        self.assertTrue(location_center_y[0]<37)
        self.assertTrue(location_center_y[1]>13)
        self.assertTrue(location_center_y[1]<16)

    def test_02_03_test_threshold_range(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".7,1"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.watershed_method.value = ID.WA_NONE
        img = two_cell_image()
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        self.assertTrue("Image" in measurements.get_object_names())
        self.assertTrue("my_object" in measurements.get_object_names())
        self.assertTrue("Threshold_FinalThreshold_my_object" in measurements.get_feature_names("Image"))
        threshold = measurements.get_current_measurement("Image","Threshold_FinalThreshold_my_object")
        self.assertTrue(threshold < .8)
        self.assertTrue(threshold > .6)
        self.assertTrue("Count_my_object" in measurements.get_feature_names("Image"))
        count = measurements.get_current_measurement("Image","Count_my_object")
        self.assertEqual(count,1)
        self.assertTrue("Location_Center_X" in measurements.get_feature_names("my_object"))
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),1)
        self.assertTrue(location_center_x[0]>8)
        self.assertTrue(location_center_x[0]<12)
        self.assertTrue("Location_Center_Y" in measurements.get_feature_names("my_object"))
        location_center_y = measurements.get_current_measurement("my_object","Location_Center_Y")
        self.assertTrue(isinstance(location_center_y,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_y.shape),1)
        self.assertTrue(location_center_y[0]>33)
        self.assertTrue(location_center_y[0]<36)
    
    def test_02_04_fill_holes(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.FILL_HOLES_OPTION_VAR).value = True
        x.variable(ID.AUTOMATIC_SMOOTHING_VAR).value = False
        x.variable(ID.SMOOTHING_SIZE_VAR).value = 0
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((40,40))
        draw_circle(img, (10,10), 7, .5)
        draw_circle(img, (30,30), 7, .5)
        img[10,10] = 0
        img[30,30] = 0
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertTrue(objects.segmented[10,10] > 0)
        self.assertTrue(objects.segmented[30,30] > 0)
        
    def test_02_05_dont_fill_holes(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.THRESHOLD_RANGE_VAR).value = ".7,1"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.FILL_HOLES_OPTION_VAR).value = False
        x.variable(ID.SMOOTHING_SIZE_VAR).value = 0
        x.variable(ID.AUTOMATIC_SMOOTHING_VAR).value = False
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((40,40))
        draw_circle(img, (10,10), 7, .5)
        draw_circle(img, (30,30), 7, .5)
        img[10,10] = 0
        img[30,30] = 0
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertTrue(objects.segmented[10,10] == 0)
        self.assertTrue(objects.segmented[30,30] == 0)
    
    def test_02_06_test_watershed_shape_shape(self):
        """Identify by local_maxima:shape & intensity:shape
        
        Create an object whose intensity is high near the middle
        but has an hourglass shape, then segment it using shape/shape
        """
        x = ID.IdentifyPrimAutomatic()
        x.image_name.value = "my_image"
        x.object_name.value = "my_object"
        x.exclude_size.value = False
        x.size_range.value = (2,10)
        x.fill_holes.value = False
        x.smoothing_filter_size.value = 0
        x.automatic_smoothing.value = 0
        x.maxima_suppression_size.value = 3
        x.automatic_suppression.value = False
        x.unclump_method.value = ID.UN_SHAPE
        x.watershed_method.value = ID.WA_DISTANCE
        img = numpy.array([[ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0,.5,.5,.5,.5,.5,.5, 0, 0, 0, 0, 0],
                           [ 0, 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0, 0,.6,.6,.6,.6,.6,.6,.6,.6,.6,.6, 0, 0, 0],
                           [ 0, 0, 0, 0,.7,.7,.7,.7,.7,.7,.7,.7, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0,.8,.9, 1, 1,.9,.8, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0,.7,.7,.7,.7,.7,.7,.7,.7, 0, 0, 0, 0],
                           [ 0, 0, 0,.6,.6,.6,.6,.6,.6,.6,.6,.6,.6, 0, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0, 0],
                           [ 0, 0, 0, 0, 0,.5,.5,.5,.5,.5,.5, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                           ])
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertEqual(numpy.max(objects.segmented),2)
    
    def test_02_07_test_watershed_shape_intensity(self):
        """Identify by local_maxima:shape & watershed:intensity
        
        Create an object with an hourglass shape to get two maxima, but
        set the intensities so that one maximum gets the middle portion
        """
        x = ID.IdentifyPrimAutomatic()
        x.image_name.value = "my_image"
        x.object_name.value = "my_object"
        x.exclude_size.value = False
        x.size_range.value = (2,10)
        x.fill_holes.value = False
        x.smoothing_filter_size.value = 0
        x.automatic_smoothing.value = 0
        x.maxima_suppression_size.value = 3
        x.automatic_suppression.value = False
        x.unclump_method.value = ID.UN_SHAPE
        x.watershed_method.value = ID.WA_INTENSITY
        img = numpy.array([[ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0,.5,.5,.5,.5,.5,.5, 0, 0, 0, 0, 0],
                           [ 0, 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0],
                           [ 0, 0, 0,.5,.5,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0, 0],
                           [ 0, 0, 0, 0,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0,.5,.5,.5,.5,.5,.5, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0,.5,.5,.5,.5,.5,.5,.5,.5, 0, 0, 0, 0],
                           [ 0, 0, 0,.4,.4,.4,.5,.5,.5,.4,.4,.4,.4, 0, 0, 0],
                           [ 0, 0,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4, 0, 0],
                           [ 0, 0,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4, 0, 0],
                           [ 0, 0,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4, 0, 0],
                           [ 0, 0,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4, 0, 0],
                           [ 0, 0, 0,.4,.4,.4,.4,.4,.4,.4,.4,.4,.4, 0, 0, 0],
                           [ 0, 0, 0, 0, 0,.4,.4,.4,.4,.4,.4, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                           ])
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertEqual(numpy.max(objects.segmented),2)
        self.assertEqual(objects.segmented[7,11],objects.segmented[7,4])
    
    def test_03_01_run_inside_pipeline(self):
        pipeline = cellprofiler.pipeline.Pipeline()
        inject_image = InjectImage("my_image", two_cell_image())
        inject_image.set_module_num(1)
        pipeline.add_module(inject_image)
        ipm = ID.IdentifyPrimAutomatic()
        ipm.set_module_num(2)
        ipm.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        ipm.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        ipm.variable(ID.EXCLUDE_SIZE_VAR).value = False
        ipm.watershed_method.value = ID.WA_NONE
        pipeline.add_module(ipm)
        measurements = pipeline.run()
        (matfd,matpath) = tempfile.mkstemp('.mat')
        matfh = os.fdopen(matfd,'wb')
        matfh.close()
        pipeline.save_measurements(matpath, measurements)
        matlab = get_matlab_instance()
        handles = matlab.load(matpath)
        handles = handles.handles
        self.assertEquals(matlab.num2str(matlab.isfield(handles,"Measurements")),'1','handles is missing Measurements')
        self.assertEquals(matlab.num2str(matlab.isfield(handles.Measurements,"Image")),'1')
        self.assertEquals(matlab.num2str(matlab.isfield(handles.Measurements.Image,"Threshold_FinalThreshold_my_object")),'1')
        thresholds = handles.Measurements.Image.Threshold_FinalThreshold_my_object
        threshold = thresholds._[0][0,0]
        #self.assertTrue(threshold < .6)
        self.assertEquals(matlab.num2str(matlab.isfield(handles.Measurements.Image,"Count_my_object")),'1')
        counts = handles.Measurements.Image.Count_my_object
        count = counts._[0][0,0]
        self.assertEqual(count,2)
        self.assertEquals(matlab.num2str(matlab.isfield(handles.Measurements,"my_object")),'1')
        self.assertEquals(matlab.num2str(matlab.isfield(handles.Measurements.my_object,"Location_Center_X")),'1')
        location_center_x = matlab.cell2mat(handles.Measurements.my_object.Location_Center_X[0])
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),2)
        self.assertTrue(location_center_x[0,0]>8)
        self.assertTrue(location_center_x[0,0]<12)
        self.assertTrue(location_center_x[1,0]>28)
        self.assertTrue(location_center_x[1,0]<32)
        self.assertEquals(matlab.num2str(matlab.isfield(handles.Measurements.my_object,"Location_Center_Y")),'1')
        location_center_y = matlab.cell2mat(handles.Measurements.my_object.Location_Center_Y[0])
        self.assertTrue(isinstance(location_center_y,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_y.shape),2)
        self.assertTrue(location_center_y[0,0]>33)
        self.assertTrue(location_center_y[0,0]<37)
        self.assertTrue(location_center_y[1,0]>13)
        self.assertTrue(location_center_y[1,0]<16)

    def test_04_01_load_matlab_12(self):
        """Test loading a Matlab version 12 IdentifyPrimAutomatic pipeline
        
        
        """
        old_r12_file = 'TUFUTEFCIDUuMCBNQVQtZmlsZSwgUGxhdGZvcm06IFBDV0lOLCBDcmVhdGVkIG9uOiBXZWQgRGVjIDMxIDExOjQxOjUxIDIwMDggICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAABSU0PAAAAuAEAAHicxVRdT8IwFO3GWEQNEYmJvu3RB2K2xAcfNTFRHgQihujjBoXUbC3ZWgM++TP8Of4Uf4ot7LMSNqfgTZpx7u45p/eytg4AMGsA6Py5w5cKllENsZJaAvchpQhPgirQwHGY/+BrYPvIdlw4sF0GAxBHlG/jMXmYT+NXd2TEXNixvXQxjw7zHOgH3XFEDF/30Ay6ffQKQTaisnv4ggJEcMgP9eVs7Euo5Fvn61NL5qCsmEMzlRf1lyCp11bU76bqD0J8TQxMqMECmOhc5Ojoko6+mNPQhagYvyrxBbbM1rkZ+ps5/EqGXwFPfHZFeGqGp4IO+Z1f3rz3pD4F7tKAGTcucWw3nneev5LRUYBVck5myyrE0zI8DZhnplWk35rUr8BtTCEOEJ2H+f/WuWKUeDZFww3obOo7Knpu/0pn2+fvTVl/zzVS+bJ9Is+ewIlP2DTRuc3RaUg6AhPnGQ7pQshAeASnqX1t+5m3/0Np/wITRl2E4bcGhN4MrP8f0vdQEf8jyV/g9ghiisbzno+89BmSvx89x1/lv5oreGXvzyJ++yV4Gme+nyx5jz+c7+ma+iii/BfqTY0Q'
        pipeline = cellprofiler.modules.tests.load_pipeline(self, old_r12_file)
        self.assertEqual(len(pipeline.modules()),1)
        module = pipeline.module(1)
        self.assertTrue(isinstance(module,cellprofiler.modules.identifyprimautomatic.IdentifyPrimAutomatic))
        self.assertTrue(module.threshold_algorithm,cellprofiler.modules.identifyprimautomatic.TM_OTSU)
        self.assertTrue(module.threshold_modifier,cellprofiler.modules.identifyprimautomatic.TM_GLOBAL)
        self.assertTrue(module.image_name == cellprofiler.variable.DO_NOT_USE)
    
    def test_04_02_load_v13(self):
        file = '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BAAAAAAAAAAFAAAACAAAAAEAAAARAAAAAQAAAAAAAAAQAAAAEQAAAG9iamVjdGdyb3VwIGluZGVwAAAAAAAAAA4AAAAwAAAABgAAAAgAAAAGAAAAAAAAAAUAAAAIAAAAAAAAAAAAAAABAAAAAAAAAAkAAAAAAAAADgAAADAAAAAGAAAACAAAAAYAAAAAAAAABQAAAAgAAAAAAAAAAAAAAAEAAAAAAAAACQAAAAAAAAAOAAAAMAAAAAYAAAAIAAAABgAAAAAAAAAFAAAACAAAAAAAAAAAAAAAAQAAAAAAAAAJAAAAAAAAAA4AAAAwAAAABgAAAAgAAAAGAAAAAAAAAAUAAAAIAAAAAAAAAAAAAAABAAAAAAAAAAkAAAAAAAAADgAAADAAAAAGAAAACAAAAAYAAAAAAAAABQAAAAgAAAAAAAAAAAAAAAEAAAAAAAAACQAAAAAAAAAOAAAAMAAAAAYAAAAIAAAABgAAAAAAAAAFAAAACAAAAAAAAAAAAAAAAQAAAAAAAAAJAAAAAAAAAA4AAAAwAAAABgAAAAgAAAAGAAAAAAAAAAUAAAAIAAAAAAAAAAAAAAABAAAAAAAAAAkAAAAAAAAADgAAADAAAAAGAAAACAAAAAYAAAAAAAAABQAAAAgAAAAAAAAAAAAAAAEAAAAAAAAACQAAAAAAAAAOAAAAMAAAAAYAAAAIAAAABgAAAAAAAAAFAAAACAAAAAAAAAAAAAAAAQAAAAAAAAAJAAAAAAAAAA4AAAAwAAAABgAAAAgAAAAGAAAAAAAAAAUAAAAIAAAAAAAAAAAAAAABAAAAAAAAAAkAAAAAAAAADgAAADAAAAAGAAAACAAAAAYAAAAAAAAABQAAAAgAAAAAAAAAAAAAAAEAAAAAAAAACQAAAAAAAAAOAAAAMAAAAAYAAAAIAAAABgAAAAAAAAAFAAAACAAAAAAAAAAAAAAAAQAAAAAAAAAJAAAAAAAAAA4AAAAwAAAABgAAAAgAAAAGAAAAAAAAAAUAAAAIAAAAAAAAAAAAAAABAAAAAAAAAAkAAAAAAAAADgAAAEgAAAAGAAAACAAAAAQAAAAAAAAABQAAAAgAAAABAAAAEgAAAAEAAAAAAAAAEAAAABIAAABvdXRsaW5lZ3JvdXAgaW5kZXAAAAAAAAAOAAAAMAAAAAYAAAAIAAAABgAAAAAAAAAFAAAACAAAAAAAAAAAAAAAAQAAAAAAAAAJAAAAAAAAAA4AAAAwAAAABgAAAAgAAAAGAAAAAAAAAAUAAAAIAAAAAAAAAAAAAAABAAAAAAAAAAkAAAAAAAAADgAAADAAAAAGAAAACAAAAAYAAAAAAAAABQAAAAgAAAAAAAAAAAAAAAEAAAAAAAAACQAAAAAAAAAOAAAAMAAAAAYAAAAIAAAABgAAAAAAAAAFAAAACAAAAAAAAAAAAAAAAQAAAAAAAAAJAAAAAAAAAA4AAACgAAAABgAAAAgAAAABAAAAAAAAAAUAAAAIAAAAAQAAAAEAAAABAAAAAAAAAA4AAABwAAAABgAAAAgAAAAEAAAAAAAAAAUAAAAIAAAAAQAAAEAAAAABAAAAAAAAABAAAABAAAAAY2VsbHByb2ZpbGVyLm1vZHVsZXMuaWRlbnRpZnlwcmltYXV0b21hdGljLklkZW50aWZ5UHJpbUF1dG9tYXRpYw4AAAAwAAAABgAAAAgAAAAJAAAAAAAAAAUAAAAIAAAAAQAAAAEAAAABAAAAAAAAAAIAAQAUAAAADgAAACgAAAAGAAAACAAAAAwAAAAAAAAABQAAAAAAAAABAAAAAAAAAAUABAABAAAADgAAADAAAAAGAAAACAAAAAkAAAAAAAAABQAAAAgAAAABAAAAAQAAAAEAAAAAAAAAAgABAA0AAAAOAAAAMAAAAAYAAAAIAAAACwAAAAAAAAAFAAAACAAAAAEAAAABAAAAAQAAAAAAAAAEAAIAAAAAAA4AAABYAAAABgAAAAgAAAABAAAAAAAAAAUAAAAIAAAAAQAAAAEAAAABAAAAAAAAAA4AAAAoAAAABgAAAAgAAAABAAAAAAAAAAUAAAAIAAAAAAAAAAEAAAABAAAAAAAAAA=='
        pipeline = cellprofiler.modules.tests.load_pipeline(self,file)
        self.assertEqual(len(pipeline.modules()),1)
        module = pipeline.module(1)
        self.assertTrue(isinstance(module,cellprofiler.modules.identifyprimautomatic.IdentifyPrimAutomatic))
        self.assertTrue(module.threshold_algorithm,cellprofiler.modules.identifyprimautomatic.TM_OTSU)
        self.assertTrue(module.threshold_modifier,cellprofiler.modules.identifyprimautomatic.TM_GLOBAL)
        self.assertTrue(module.image_name == 'None')
    
    def test_05_01_discard_large(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = True
        x.variable(ID.SIZE_RANGE_VAR).value = '10,40'
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((200,200))
        draw_circle(img,(100,100),50,.5)
        draw_circle(img,(25,25),20,.5)
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertEqual(objects.segmented[25,25],1,"The small object was not there")
        self.assertEqual(objects.segmented[100,100],0,"The large object was not filtered out")
        self.assertTrue(objects.small_removed_segmented[25,25]>0,"The small object was not in the small_removed label set")
        self.assertTrue(objects.small_removed_segmented[100,100]>0,"The large object was not in the small-removed label set")
        self.assertTrue(objects.unedited_segmented[25,25],"The small object was not in the unedited set")
        self.assertTrue(objects.unedited_segmented[100,100],"The large object was not in the unedited set")
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),1)

    def test_05_02_keep_large(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.SIZE_RANGE_VAR).value = '10,40'
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((200,200))
        draw_circle(img,(100,100),50,.5)
        draw_circle(img,(25,25),20,.5)
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertTrue(objects.segmented[25,25],"The small object was not there")
        self.assertTrue(objects.segmented[100,100],"The large object was filtered out")
        self.assertTrue(objects.unedited_segmented[25,25],"The small object was not in the unedited set")
        self.assertTrue(objects.unedited_segmented[100,100],"The large object was not in the unedited set")
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),2)

    def test_05_03_discard_small(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = True
        x.variable(ID.SIZE_RANGE_VAR).value = '40,60'
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((200,200))
        draw_circle(img,(100,100),50,.5)
        draw_circle(img,(25,25),20,.5)
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        self.assertEqual(objects.segmented[25,25],0,"The small object was not filtered out")
        self.assertEqual(objects.segmented[100,100],1,"The large object was not present")
        self.assertTrue(objects.small_removed_segmented[25,25]==0,"The small object was in the small_removed label set")
        self.assertTrue(objects.small_removed_segmented[100,100]>0,"The large object was not in the small-removed label set")
        self.assertTrue(objects.unedited_segmented[25,25],"The small object was not in the unedited set")
        self.assertTrue(objects.unedited_segmented[100,100],"The large object was not in the unedited set")
        location_center_x = measurements.get_current_measurement("my_object","Location_Center_X")
        self.assertTrue(isinstance(location_center_x,numpy.ndarray))
        self.assertEqual(numpy.product(location_center_x.shape),1)

    def test_05_02_discard_edge(self):
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.SIZE_RANGE_VAR).value = '10,40'
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((100,100))
        centers = [(50,50),(10,50),(50,10),(90,50),(50,90)]
        present = [ True,  False,  False,  False,  False]
        for center in centers:
            draw_circle(img,center,15,.5)
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        for center, p in zip(centers,present):
            if p:
                self.assertTrue(objects.segmented[center[0],center[1]] > 0)
            else:
                self.assertTrue(objects.segmented[center[0],center[1]] == 0)
            self.assertTrue(objects.unedited_segmented[center[0],center[1]] > 0)
            self.assertTrue(objects.small_removed_segmented[center[0],center[1]] > 0)

    def test_05_03_discard_with_mask(self):
        """Check discard of objects that are on the border of a mask"""
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.SIZE_RANGE_VAR).value = '10,40'
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((200,200))
        centers = [(100,100),(30,100),(100,30),(170,100),(100,170)]
        present = [ True,  False,  False,  False,  False]
        for center in centers:
            draw_circle(img,center,15,.5)
        mask = numpy.zeros((200,200))
        mask[25:175,25:175]=1
        image = cellprofiler.cpimage.Image(img,mask)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        objects = object_set.get_objects("my_object")
        for center, p in zip(centers,present):
            if p:
                self.assertTrue(objects.segmented[center[0],center[1]] > 0)
            else:
                self.assertTrue(objects.segmented[center[0],center[1]] == 0)
            self.assertTrue(objects.unedited_segmented[center[0],center[1]] > 0)
            self.assertTrue(objects.small_removed_segmented[center[0],center[1]] > 0)
    def test_06_01_regression_diagonal(self):
        """Regression test - was using one-connected instead of 3-connected structuring element"""
        x = ID.IdentifyPrimAutomatic()
        x.variable(ID.OBJECT_NAME_VAR).value = "my_object"
        x.variable(ID.IMAGE_NAME_VAR).value = "my_image"
        x.variable(ID.EXCLUDE_SIZE_VAR).value = False
        x.variable(ID.SMOOTHING_SIZE_VAR).value = 0
        x.variable(ID.AUTOMATIC_SMOOTHING_VAR).value = False
        x.watershed_method.value = ID.WA_NONE
        img = numpy.zeros((10,10))
        img[4,4]=1
        img[5,5]=1
        image = cellprofiler.cpimage.Image(img)
        image_set_list = cellprofiler.cpimage.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        image_set.providers.append(cellprofiler.cpimage.VanillaImageProvider("my_image",image))
        object_set = cellprofiler.objects.ObjectSet()
        measurements = cellprofiler.measurements.Measurements()
        pipeline = cellprofiler.pipeline.Pipeline()
        x.run(pipeline,image_set,object_set,measurements,None)
        self.assertEqual(len(object_set.object_names),1)
        self.assertTrue("my_object" in object_set.object_names)
        objects = object_set.get_objects("my_object")
        segmented = objects.segmented
        self.assertTrue(numpy.all(segmented[img>0] == 1))
        self.assertTrue(numpy.all(img[segmented==1] > 0))

def one_cell_image():
    img = numpy.zeros((25,25))
    draw_circle(img,(10,15),5, .5)
    return img

def two_cell_image():
    img = numpy.zeros((50,50))
    draw_circle(img,(10,35),5, .8)
    draw_circle(img,(30,15),5, .6)
    return img
    
def draw_circle(img,center,radius,value):
    x,y=numpy.mgrid[0:img.shape[0],0:img.shape[1]]
    distance = numpy.sqrt((x-center[0])*(x-center[0])+(y-center[1])*(y-center[1]))
    img[distance<=radius]=value