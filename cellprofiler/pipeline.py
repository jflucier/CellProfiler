"""Pipeline.py - an ordered set of modules to be executed

CellProfiler is distributed under the GNU General Public License.
See the accompanying file LICENSE for details.

Copyright (c) 2003-2009 Massachusetts Institute of Technology
Copyright (c) 2009-2013 Broad Institute
All rights reserved.

Please see the AUTHORS file for credits.

Website: http://www.cellprofiler.org
"""
from __future__ import with_statement

__version__ = "$Revision$"

import hashlib
import logging
import gc
import numpy as np
import scipy.io.matlab
import scipy
try:
    #implemented in scipy.io.matlab.miobase.py@5582
    from scipy.io.matlab.miobase import MatReadError
    has_mat_read_error = True
except:
    has_mat_read_error = False
    
import os
import StringIO
import sys
import tempfile
import traceback
import datetime
import traceback
import threading
import urlparse
import urllib2
import re

logger = logging.getLogger(__name__)
pipeline_stats_logger = logging.getLogger("PipelineStatistics")
import cellprofiler.cpmodule
import cellprofiler.preferences as cpprefs
import cellprofiler.cpimage as cpi
import cellprofiler.measurements as cpmeas
import cellprofiler.objects as cpo
import cellprofiler.workspace as cpw
import cellprofiler.settings as cps
from cellprofiler.utilities.utf16encode import utf16encode, utf16decode
from cellprofiler.matlab.cputils import make_cell_struct_dtype, new_string_cell_array, encapsulate_strings_in_arrays

'''The measurement name of the image number'''
IMAGE_NUMBER = cpmeas.IMAGE_NUMBER
GROUP_NUMBER = cpmeas.GROUP_NUMBER
GROUP_INDEX = cpmeas.GROUP_INDEX
CURRENT = 'Current'
NUMBER_OF_IMAGE_SETS     = 'NumberOfImageSets'
NUMBER_OF_MODULES        = 'NumberOfModules'
SET_BEING_ANALYZED       = 'SetBeingAnalyzed'
SAVE_OUTPUT_HOW_OFTEN    = 'SaveOutputHowOften'
TIME_STARTED             = 'TimeStarted'
STARTING_IMAGE_SET       = 'StartingImageSet'
STARTUP_DIRECTORY        = 'StartupDirectory'
DEFAULT_MODULE_DIRECTORY = 'DefaultModuleDirectory'
DEFAULT_IMAGE_DIRECTORY  = 'DefaultImageDirectory'
DEFAULT_OUTPUT_DIRECTORY = 'DefaultOutputDirectory'
IMAGE_TOOLS_FILENAMES    = 'ImageToolsFilenames'
IMAGE_TOOL_HELP          = 'ImageToolHelp'
PREFERENCES              = 'Preferences'
PIXEL_SIZE               = 'PixelSize'
SKIP_ERRORS              = 'SkipErrors'
INTENSITY_COLOR_MAP      = 'IntensityColorMap'
LABEL_COLOR_MAP          = 'LabelColorMap'
STRIP_PIPELINE           = 'StripPipeline'
DISPLAY_MODE_VALUE       = 'DisplayModeValue'
DISPLAY_WINDOWS          = 'DisplayWindows'
FONT_SIZE                = 'FontSize'
IMAGES                   = 'Images'
MEASUREMENTS             = 'Measurements'
PIPELINE                 = 'Pipeline'    
SETTINGS                  = 'Settings'
VARIABLE_VALUES           = 'VariableValues'
VARIABLE_INFO_TYPES       = 'VariableInfoTypes'
MODULE_NAMES              = 'ModuleNames'
PIXEL_SIZE                = 'PixelSize'
NUMBERS_OF_VARIABLES      = 'NumbersOfVariables'
VARIABLE_REVISION_NUMBERS = 'VariableRevisionNumbers'
MODULE_REVISION_NUMBERS   = 'ModuleRevisionNumbers'
MODULE_NOTES              = 'ModuleNotes'
CURRENT_MODULE_NUMBER     = 'CurrentModuleNumber'
SHOW_WINDOW                = 'ShowFrame'
BATCH_STATE               = 'BatchState'
EXIT_STATUS               = 'Exit_Status'
SETTINGS_DTYPE = np.dtype([(VARIABLE_VALUES, '|O4'), 
                           (VARIABLE_INFO_TYPES, '|O4'), 
                           (MODULE_NAMES, '|O4'), 
                           (NUMBERS_OF_VARIABLES, '|O4'), 
                           (PIXEL_SIZE, '|O4'), 
                           (VARIABLE_REVISION_NUMBERS, '|O4'), 
                           (MODULE_REVISION_NUMBERS, '|O4'), 
                           (MODULE_NOTES, '|O4'),
                           (SHOW_WINDOW, '|O4'),
                           (BATCH_STATE, '|O4')])
CURRENT_DTYPE = make_cell_struct_dtype([ NUMBER_OF_IMAGE_SETS,
                                         SET_BEING_ANALYZED, NUMBER_OF_MODULES, 
                                         SAVE_OUTPUT_HOW_OFTEN,TIME_STARTED, 
                                         STARTING_IMAGE_SET,
                                         STARTUP_DIRECTORY, 
                                         DEFAULT_OUTPUT_DIRECTORY, 
                                         DEFAULT_IMAGE_DIRECTORY, 
                                         IMAGE_TOOLS_FILENAMES, 
                                         IMAGE_TOOL_HELP])
PREFERENCES_DTYPE = make_cell_struct_dtype([PIXEL_SIZE, 
                                            DEFAULT_MODULE_DIRECTORY, 
                                            DEFAULT_OUTPUT_DIRECTORY, 
                                            DEFAULT_IMAGE_DIRECTORY, 
                                            INTENSITY_COLOR_MAP, 
                                            LABEL_COLOR_MAP,
                                            STRIP_PIPELINE, SKIP_ERRORS, 
                                            DISPLAY_MODE_VALUE, FONT_SIZE,
                                            DISPLAY_WINDOWS])

'''Save pipeline in Matlab format'''
FMT_MATLAB = "Matlab"

'''Save pipeline in native format'''
FMT_NATIVE = "Native"

'''The current pipeline file format version'''
NATIVE_VERSION = 2

H_VERSION = 'Version'
H_SVN_REVISION = 'SVNRevision'
H_DATE_REVISION = 'DateRevision'
'''A pipeline file header variable for faking a matlab pipeline file'''
H_FROM_MATLAB = 'FromMatlab'

'''The cookie that identifies a file as a CellProfiler pipeline'''
COOKIE = "CellProfiler Pipeline: http://www.cellprofiler.org"

'''HDF5 file header according to the specification

see http://www.hdfgroup.org/HDF5/doc/H5.format.html#FileMetaData
'''
HDF5_HEADER = (chr(137) + chr(72) + chr(68) + chr(70) + chr(13) + chr(10) +
               chr (26) + chr(10))
C_PIPELINE = "Pipeline"
F_PIPELINE = "Pipeline"
M_PIPELINE = "_".join((C_PIPELINE,F_PIPELINE))

def add_all_images(handles,image_set, object_set):
    """ Add all images to the handles structure passed
    
    Add images to the handles structure, for example in the Python sandwich.
    """
    images = {}
    for provider in image_set.providers:
        name = provider.name()
        image = image_set.get_image(name)
        images[name] = image.image
        if image.has_mask:
            images['CropMask'+name] = image.mask
    
    for object_name in object_set.object_names:
        objects = object_set.get_objects(object_name)
        images['Segmented'+object_name] = objects.segmented
        if objects.has_unedited_segmented():
            images['UneditedSegmented'+object_name] = objects.unedited_segmented
        if objects.has_small_removed_segmented():
            images['SmallRemovedSegmented'+object_name] = objects.small_removed_segmented
    
    npy_images = np.ndarray((1,1),dtype=make_cell_struct_dtype(images.keys()))
    for key,image in images.iteritems():
        npy_images[key][0,0] = image
    handles[PIPELINE]=npy_images

def map_feature_names(feature_names, max_size=63):
    '''Map feature names to legal Matlab field names
    
    returns a dictionary where the key is the field name and
    the value is the feature name.
    '''
    mapping = {}
    seeded = False
    def shortest_first(a,b):
        return -1 if len(a) < len(b) else 1 if len(b) < len(a) else cmp(a,b)
    
    for feature_name in sorted(feature_names,shortest_first):
        if len(feature_name) > max_size:
            name = feature_name
            to_remove = len(feature_name) - max_size
            remove_count = 0
            for to_drop in (('a','e','i','o','u'),
                            ('b','c','d','f','g','h','j','k','l','m','n',
                             'p','q','r','s','t','v','w','x','y','z'),
                            ('A','B','C','D','E','F','G','H','I','J','K',
                             'L','M','N','O','P','Q','R','S','T','U','V',
                             'W','X','Y','Z')):
                for index in range(len(name)-1,-1,-1):
                    if name[index] in to_drop:
                        name = name[:index]+name[index+1:]
                        remove_count += 1
                        if remove_count == to_remove:
                            break
                if remove_count == to_remove:
                    break
            if name in mapping.keys() or len(name) > max_size:
                # Panic mode - a duplication
                if not seeded:
                    np.random.seed(0)
                    seeded = True
                while True:
                    npname = np.fromstring(feature_name, '|S1')
                    indices = np.random.permutation(len(name))[:max_size]
                    indices.sort()
                    name = npname[indices]
                    name = name.tostring()
                    if not name in mapping.keys():
                        break
        else:
            name = feature_name
        mapping[name] = feature_name
    return mapping
        
def add_all_measurements(handles, measurements):
    """Add all measurements from our measurements object into the numpy structure passed
    
    """
    object_names = [name for name in measurements.get_object_names()
                    if len(measurements.get_feature_names(name)) > 0]
    measurements_dtype = make_cell_struct_dtype(object_names)
    npy_measurements = np.ndarray((1,1),dtype=measurements_dtype)
    handles[MEASUREMENTS]=npy_measurements
    image_numbers = measurements.get_image_numbers()
    max_image_number = np.max(image_numbers)
    has_image_number = np.zeros(max_image_number + 1, bool)
    has_image_number[image_numbers] = True
    for object_name in object_names:
        if object_name == cpmeas.EXPERIMENT:
            continue
        mapping = map_feature_names(measurements.get_feature_names(object_name))
        object_dtype = make_cell_struct_dtype(mapping.keys())
        object_measurements = np.ndarray((1,1),dtype=object_dtype)
        npy_measurements[object_name][0,0] = object_measurements
        for field, feature_name in mapping.iteritems():
            feature_measurements = np.ndarray((1, max_image_number),
                                              dtype='object')
            object_measurements[field][0,0] = feature_measurements
            for i in np.argwhere(~ has_image_number[1:]).flatten():
                feature_measurements[0, i] = np.zeros(0)
            for i in measurements.get_image_numbers():
                ddata = measurements.get_measurement(object_name, feature_name, i)
                if np.isscalar(ddata) and np.isreal(ddata):
                    feature_measurements[0, i-1] = np.array([ddata])
                elif ddata is not None:
                    feature_measurements[0,i-1] = ddata
                else:
                    feature_measurements[0, i-1] = np.zeros(0)
    if cpmeas.EXPERIMENT in measurements.object_names:
        mapping = map_feature_names(measurements.get_feature_names(cpmeas.EXPERIMENT))
        object_dtype = make_cell_struct_dtype(mapping.keys())
        experiment_measurements = np.ndarray((1,1), dtype=object_dtype)
        npy_measurements[cpmeas.EXPERIMENT][0,0] = experiment_measurements
        for field, feature_name in mapping.iteritems():
            feature_measurements = np.ndarray((1,1),dtype='object')
            feature_measurements[0,0] = measurements.get_experiment_measurement(feature_name)
            experiment_measurements[field][0,0] = feature_measurements


_evt_modulerunner_done_id = None
_evt_modulerunner_eventtype = None

def evt_modulerunner_done_id():
    """Initialize _evt_modulerunner_done_id inside this function
    instead of at the top level so that the module will not require wx
    when the GUI stuff is not being used."""
    import wx
    global _evt_modulerunner_done_id
    if _evt_modulerunner_done_id is None:
        _evt_modulerunner_done_id = wx.NewId()
    return _evt_modulerunner_done_id

def evt_modulerunner_event_type():
    """Initialize the module runner event type"""
    import wx
    global _evt_modulerunner_eventtype
    if _evt_modulerunner_eventtype is None:
        _evt_modulerunner_eventtype = wx.NewEventType()
    return _evt_modulerunner_eventtype

def evt_modulerunner_done(win, func):
    done_id = evt_modulerunner_done_id()
    event_type = evt_modulerunner_event_type()
    win.Connect(done_id, done_id, event_type, func)

class ModuleRunner(threading.Thread):
    """Worker thread that executes the run() method of a module."""
    def __init__(self, module, workspace, notify_window):
        super(ModuleRunner, self).__init__()
        self.module = module
        self.workspace = workspace
        self.notify_window = notify_window
        self.paused = False
        self.exited_run = False
        self.exception = None
        self.tb = None
        workspace.add_disposition_listener(self.on_disposition_changed)
    
    def on_disposition_changed(self, event):
        '''Callback to listen for changes in the workspace disposition
        
        This gets called when a module decides to pause, continue,
        or cancel running the pipeline. We want to postpone posting done
        during pause and post done if we've finished running and
        we're switching from paused to not paused
        '''
        if event.disposition == cpw.DISPOSITION_PAUSE:
            self.paused = True
        elif self.paused:
            self.paused = False
            if self.exited_run:
                self.post_done()
            
    def run(self):
        try:
            self.module.run(self.workspace)
        except Exception, instance:
            self.exception = instance
            self.tb = sys.exc_info()[2]
            logger.warning("Intercepted exception while running module",
                           exc_info=True)
            if os.getenv('CELLPROFILER_RERAISE') is not None:
                raise
        if not self.paused:
            self.post_done()
        self.exited_run = True
        
    def post_done(self):
        post_module_runner_done_event(self.notify_window)
        
def post_module_runner_done_event(window):
    import wx

    # Defined here because the module should not depend on wx.
    class ModuleRunnerDoneEvent(wx.PyEvent):
        """In spite of its name, this event is posted both when a module
        runner is done (i.e., when the module's run() method is finished)
        and then again when run_with_yield has displayed the module's
        results and collected its measurements."""
        def __init__(self):
            wx.PyEvent.__init__(self)
            self.SetEventType(evt_modulerunner_event_type())
            self.SetId(evt_modulerunner_done_id())
        def RequestMore(self):
            "For now, make this work with code written for IdleEvent."
            pass

    wx.PostEvent(window, ModuleRunnerDoneEvent())


class Pipeline(object):
    """A pipeline represents the modules that a user has put together
    to analyze their images.
    
    """

    def __init__(self):
        self.__modules = [];
        self.__listeners = [];
        self.__measurement_columns = {}
        self.__measurement_column_hash = None
        self.__test_mode = False
        self.__settings = []
        self.__undo_stack = []
        self.__undo_start = None
    
    def copy(self):
        '''Create a copy of the pipeline modules and settings'''
        fd = StringIO.StringIO()
        self.save(fd)
        pipeline = Pipeline()
        fd.seek(0)
        pipeline.load(fd)
        return pipeline
    
    def settings_hash(self):
        '''Return a hash of the module settings
        
        This function can be used to invalidate a cached calculation
        that's based on pipeline settings - if the settings change, the
        hash changes and the calculation must be performed again.
        
        We use secure hashing functions which are really good at avoiding
        collisions for small changes in data.
        '''
        h = hashlib.md5()
        for module in self.modules():
            h.update(module.module_name)
            for setting in module.settings():
                h.update(setting.unicode_value.encode('utf-8'))
        return h.digest()

    def create_from_handles(self,handles):
        """Read a pipeline's modules out of the handles structure
        
        """
        self.__modules = [];
        try:
            settings = handles[SETTINGS][0,0]
            module_names = settings[MODULE_NAMES]
        except Exception,instance:
            logger.error("Failed to load pipeline", exc_info=True)
            e = LoadExceptionEvent(instance, None)
            self.notify_listeners(e)
            return
        module_count = module_names.shape[1]
        real_module_num = 1
        for module_num in range(1,module_count+1):
            idx = module_num-1
            module_name = module_names[0,idx][0]
            module = None
            try:
                module = self.instantiate_module(module_name)
                module.create_from_handles(handles, module_num)
                module.module_num = real_module_num
            except Exception,instance:
                logger.error("Failed to load pipeline", exc_info=True)
                number_of_variables = settings[NUMBERS_OF_VARIABLES][0,idx]
                module_settings = [settings[VARIABLE_VALUES][idx, i]
                                   for i in range(number_of_variables)]
                module_settings = [('' if np.product(x.shape) == 0
                                    else str(x[0])) if isinstance(x, np.ndarray)
                                   else str(x)
                                   for x in module_settings]
                                   
                event = LoadExceptionEvent(instance,module, module_name,
                                           module_settings)
                self.notify_listeners(event)
                if event.cancel_run:
                    # The pipeline is somewhat loaded at this point
                    # so we break the loop and clean up as well as we can
                    break
            if module is not None:    
                self.__modules.append(module)
                real_module_num += 1
        for module in self.__modules:
            module.post_pipeline_load(self)
            
        self.notify_listeners(PipelineLoadedEvent())
    
    def instantiate_module(self,module_name):
        import cellprofiler.modules
        return cellprofiler.modules.instantiate_module(module_name)

    def reload_modules(self):
        """Reload modules from source, and attempt to update pipeline to new versions.
        Returns True if pipeline was successfully updated.

        """
        # clear previously seen errors on reload
        import cellprofiler.gui.errordialog
        cellprofiler.gui.errordialog.clear_old_errors()
        import cellprofiler.modules
        reload(cellprofiler.modules)
        cellprofiler.modules.reload_modules()
        # attempt to reinstantiate pipeline with new modules
        try:
            self.copy()  # if this fails, we probably can't reload
            fd = StringIO.StringIO()
            self.save(fd)
            fd.seek(0)
            self.loadtxt(fd, raise_on_error=True)
            return True
        except Exception, e:
            logging.warning("Modules reloaded, but could not reinstantiate pipeline with new versions.", exc_info=True)
            return False

    def save_to_handles(self):
        """Create a numpy array representing this pipeline
        
        """
        settings = np.ndarray(shape=[1,1],dtype=SETTINGS_DTYPE)
        handles = {SETTINGS:settings }
        setting = settings[0,0]
        # The variables are a (modules,max # of variables) array of cells (objects)
        # where an empty cell is a (1,0) array of float64

        try:
            variable_count = max([len(module.settings()) for module in self.modules()])
        except:
            for module in self.modules():
                if not isinstance(module.settings(), list):
                    raise ValueError('Module %s.settings() did not return a list\n value: %s'%(module.module_name, module.settings()))
                raise

        module_count = len(self.modules())
        setting[VARIABLE_VALUES] =          new_string_cell_array((module_count,variable_count))
        # The variable info types are similarly shaped
        setting[VARIABLE_INFO_TYPES] =      new_string_cell_array((module_count,variable_count))
        setting[MODULE_NAMES] =             new_string_cell_array((1,module_count))
        setting[NUMBERS_OF_VARIABLES] =     np.ndarray((1,module_count),
                                                       dtype=np.dtype('uint8'))
        setting[PIXEL_SIZE] =               cpprefs.get_pixel_size() 
        setting[VARIABLE_REVISION_NUMBERS] =np.ndarray((1,module_count),
                                                       dtype=np.dtype('uint8'))
        setting[MODULE_REVISION_NUMBERS] =  np.ndarray((1,module_count),
                                                       dtype=np.dtype('uint16'))
        setting[MODULE_NOTES] =             new_string_cell_array((1,module_count))
        setting[SHOW_WINDOW] =               np.ndarray((1,module_count),
                                                       dtype=np.dtype('uint8'))
        setting[BATCH_STATE] = np.ndarray((1,module_count),
                                          dtype=np.dtype('object'))
        for i in range(module_count):
            setting[BATCH_STATE][0,i] = np.zeros((0,),np.uint8)
            
        for module in self.modules():
            module.save_to_handles(handles)
        return handles
    
    def load(self, fd_or_filename):
        """Load the pipeline from a file
        
        fd_or_filename - either the name of a file or a file-like object
        """
        filename = None
        if hasattr(fd_or_filename,'seek') and hasattr(fd_or_filename,'read'):
            fd = fd_or_filename
            needs_close = False
        elif hasattr(fd_or_filename, 'read') and hasattr(fd_or_filename, 'url'):
            # This is a URL file descriptor. Read into a StringIO so that
            # seek is available.
            fd = StringIO.StringIO()
            while True:
                text = fd_or_filename.read()
                if len(text) == 0:
                    break
                fd.write(text)
            fd.seek(0)
        elif os.path.exists(fd_or_filename):
            fd = open(fd_or_filename,'rb')
            needs_close = True
            filename = fd_or_filename
        else:
            # Assume is string URL
            parsed_path = urlparse.urlparse(fd_or_filename)
            if len(parsed_path.scheme) < 2:
                raise IOError("Could not find file, " + fd_or_filename)
            fd = urllib2.urlopen(fd_or_filename)
            return self.load(fd)
        header = fd.read(len(COOKIE))
        if header == COOKIE:
            fd.seek(0)
            self.loadtxt(fd)
            return
        if needs_close:
            fd.close()
        else:
            fd.seek(0)
        if header[:8] == HDF5_HEADER:
            if filename is None:
                fid, filename = tempfile.mkstemp(".h5")
                fd_out = os.fdopen(fid, "wb")
                fd_out.write(fd.read())
                fd_out.close()
                self.load(filename)
                os.unlink(filename)
                return
            else:
                m = cpmeas.load_measurements(filename)
                pipeline_text = m.get_experiment_measurement(M_PIPELINE)
                pipeline_text = pipeline_text.encode('us-ascii')
                self.load(StringIO.StringIO(pipeline_text))
                return
                
        if has_mat_read_error:
            try:
                handles=scipy.io.matlab.mio.loadmat(fd_or_filename, 
                                                    struct_as_record=True)
            except MatReadError:
                logging.error("Caught exception in Matlab reader\n", exc_info=True)
                e = MatReadError(
                    "%s is an unsupported .MAT file, most likely a measurements file.\nYou can load this as a pipeline if you load it as a pipeline using CellProfiler 1.0 and then save it to a different file.\n" %
                    fd_or_filename)
                self.notify_listeners(LoadExceptionEvent(e, None))
                return
            except Exception, e:
                logging.error("Tried to load corrupted .MAT file: %s\n" % fd_or_filename,
                              exc_info = True)
                self.notify_listeners(LoadExceptionEvent(e, None))
                return
        else:
            handles=scipy.io.matlab.mio.loadmat(fd_or_filename, 
                                                struct_as_record=True)
            
        if handles.has_key("handles"):
            #
            # From measurements...
            #
            handles=handles["handles"][0,0]
        self.create_from_handles(handles)
        self.__settings = [[str(setting) for setting in module.settings()]
                           for module in self.modules()]
        self.__undo_stack = []
    
    def loadtxt(self, fd_or_filename, raise_on_error=False):
        '''Load a pipeline from a text file
        
        fd_or_filename - either a path to a file or a file-descriptor-like
                         object.
        raise_on_error - if there is an error loading the pipeline, raise an
                         exception rather than generating a LoadException event.

        See savetxt for more comprehensive documentation.
        '''
        from cellprofiler.utilities.version import version_number as cp_version_number
        if hasattr(fd_or_filename,'seek') and hasattr(fd_or_filename,'read'):
            fd = fd_or_filename
        else:
            fd = open(fd_or_filename,'r')
        def rl():
            '''Read a line from fd'''
            try:
                line = fd.next()
                if line is None:
                    return None
                line = line.strip("\r\n")
                return line
            except StopIteration:
                return None
        
        header = rl()
        if header != COOKIE:
            raise NotImplementedError('Invalid header: "%s"'%header)
        version = NATIVE_VERSION
        from_matlab = False
        do_utf16_decode = False
        while True:
            line = rl()
            if line is None:
                raise ValueError("Pipeline file unexpectedly truncated before module section")
            elif len(line.strip()) == 0:
                break
            kwd, value = line.split(':')
            if kwd == H_VERSION:
                version = int(value)
                if version > NATIVE_VERSION:
                    raise ValueError("Pipeline file version is %d.\nCellProfiler can only read version %d or less.\nPlease upgrade to the latest version of CellProfiler." %
                                     (version, NATIVE_VERSION))
                elif version > 1:
                    do_utf16_decode = True
            elif kwd in (H_SVN_REVISION, H_DATE_REVISION):
                pipeline_version = int(value)
                CURRENT_VERSION = cp_version_number
                if pipeline_version > CURRENT_VERSION:
                    if cpprefs.get_headless():
                        logging.warning(
                            ('Your pipeline version is %d but you are '
                             'running CellProfiler version %d. '
                            'Loading this pipeline may fail or have '
                            'unpredictable results.')
                            % (pipeline_version, CURRENT_VERSION))
                    else:
                        try:
                            import wx
                            if wx.GetApp():
                                dlg = wx.MessageDialog(
                                    parent = None,
                                    message = 'Your pipeline version is %d but you are running CellProfiler version %d. \nLoading this pipeline may fail or have unpredictable results. Continue?' % (pipeline_version, CURRENT_VERSION),
                                    caption = 'Pipeline version mismatch',
                                    style = wx.OK | wx.CANCEL | wx.ICON_QUESTION)
                                if dlg.ShowModal() != wx.ID_OK:
                                    dlg.Destroy()
                                    return None
                                dlg.Destroy()
                            else:
                                raise Exception  # fall through to sys.stderr.write
                        except:
                            logger.error('Your pipeline version is %d but you are running CellProfiler version %d. \nLoading this pipeline may fail or have unpredictable results.\n' %(pipeline_version, CURRENT_VERSION))
                else:
                    if ((not cpprefs.get_headless()) and
                        pipeline_version < CURRENT_VERSION):
                        from cellprofiler.gui.errordialog import show_warning
                        show_warning(
        "Pipeline saved with old version of CellProfiler",
        "Your pipeline was saved using an old version\n"
        "of CellProfiler (version %d). The current version\n"
        "of CellProfiler can load and run this pipeline, but\n"
        "if you make changes to it and save, the older version\n"
        "of CellProfiler (perhaps the version your collaborator\n"
        "has?) may not be able to load it.\n\n"
        "You can ignore this warning if you do not plan to save\n"
        "this pipeline or if you will only use it with this or\n"
        "later versions of CellProfiler." % pipeline_version,
        cpprefs.get_warn_about_old_pipeline,
        cpprefs.set_warn_about_old_pipeline)

                    pipeline_stats_logger.info("Pipeline saved with CellProfiler version %d", pipeline_version)
            elif kwd == H_FROM_MATLAB:
                from_matlab = bool(value)
            else:
                print line
        
        #
        # The module section
        #
        new_modules = []
        module_number = 1
        skip_attributes = ['svn_version','module_num']
        while True:
            line = rl()
            if line is None:
                break
            settings = []
            try:
                module = None
                module_name = None
                split_loc = line.find(':')
                if split_loc == -1:
                    raise ValueError("Invalid format for module header: %s" % line)
                module_name = line[:split_loc].strip()
                attribute_string = line[(split_loc+1):]
                #
                # Decode the settings
                #
                last_module = False
                while True:
                    line = rl()
                    if line is None:
                        last_module = True
                        break
                    if len(line.strip()) == 0:
                        break
                    if len(line.split(':')) != 2:
                        raise ValueError("Invalid format for setting: %s" % line)
                    text, setting = line.split(':')
                    setting = setting.decode('string_escape')
                    if do_utf16_decode:
                        setting = utf16decode(setting)
                    settings.append(setting)
                #
                # Set up the module
                #
                module_name = module_name.decode('string_escape')
                module = self.instantiate_module(module_name)
                module.module_num = module_number
                #
                # Decode the attributes. These are turned into strings using
                # repr, so True -> 'True', etc. They are then encoded using
                # Pipeline.encode_txt.
                #
                if (len(attribute_string) < 2 or attribute_string[0] != '[' or
                    attribute_string[-1] != ']'):
                    raise ValueError("Invalid format for attributes: %s" %
                                     attribute_string)
                attribute_strings = attribute_string[1:-1].split('|')
                variable_revision_number = None
                # make batch_state decodable from text pipelines
                array = np.array
                uint8 = np.uint8
                for a in attribute_strings:
                    if len(a.split(':')) != 2:
                        raise ValueError("Invalid attribute string: %s" % a)
                    attribute, value = a.split(':')
                    value = value.decode('string_escape')
                    value = eval(value)
                    if attribute == 'variable_revision_number':
                        variable_revision_number = value
                    elif attribute in skip_attributes:
                        pass
                    else:
                        setattr(module, attribute, value)
                if variable_revision_number is None:
                    raise ValueError("Module %s did not have a variable revision # attribute" % module_name)
                module.set_settings_from_values(settings,
                                                variable_revision_number,
                                                module_name, from_matlab)
            except Exception, instance:
                if raise_on_error:
                    raise
                logging.error("Failed to load pipeline", exc_info=True)
                event = LoadExceptionEvent(instance, module,  module_name,
                                           settings)
                self.notify_listeners(event)
                if event.cancel_run:
                    break
            if module is not None:
                new_modules.append(module)
                module_number += 1

        self.__modules = new_modules
        self.__settings = [[str(setting) for setting in module.settings()]
                           for module in self.modules()]
        for module in self.modules():
            module.post_pipeline_load(self)
        self.notify_listeners(PipelineLoadedEvent())
        self.__undo_stack = []
        
    def save(self, fd_or_filename, format=FMT_NATIVE):
        """Save the pipeline to a file
        
        fd_or_filename - either a file descriptor or the name of the file
        """
        if format == FMT_MATLAB:
            handles = self.save_to_handles()
            self.savemat(fd_or_filename,handles)
        elif format == FMT_NATIVE:
            self.savetxt(fd_or_filename)
        else:
            raise NotImplementedError("Unknown pipeline file format: %s" %
                                      format)
    
    def encode_txt(self, s):
        '''Encode a string for saving in the text format
        
        s - input string
        Encode for automatic decoding using the 'string_escape' decoder.
        We encode the special characters, '[', ':', '|' and ']' using the '\\x'
        syntax.
        '''
        s = s.encode('string_escape')
        s = s.replace(':','\\x3A')
        s = s.replace('|','\\x7C')
        s = s.replace('[','\\x5B').replace(']','\\x5D')
        return s
        
    def savetxt(self, fd_or_filename, modules_to_save = None):
        '''Save the pipeline in a text format
        
        fd_or_filename - can be either a "file descriptor" with a "write"
                         attribute or the path to the file to write.
        modules_to_save - if present, the module numbers of the modules to save
                         
        The format of the file is the following:
        Strings are encoded using a backslash escape sequence. The colon
        character is encoded as \\x3A if it should happen to appear in a string
        and any non-printing character is encoded using the \\x## convention.
        
        Line 1: The cookie, identifying this as a CellProfiler pipeline file.
        The header, i
        Line 2: "Version:#" the file format version #
        Line 3: "DateRevision:#" the version # of the CellProfiler
                that wrote this file (date encoded as int, see cp.utitlities.version)
        Line 4: blank
        
        The module list follows. Each module has a header composed of
        the module name, followed by attributes to be set on the module
        using setattr (the string following the attribute is first evaluated
        using eval()). For instance:
        Align:[show_window:True|notes='Align my image']
        
        The settings follow. Each setting has text and a value. For instance,
        Enter object name:Nuclei
        '''
        from cellprofiler.utilities.version import version_number
        if hasattr(fd_or_filename,"write"):
            fd = fd_or_filename
            needs_close = False
        else:
            fd = open(fd_or_filename,"wt")
            needs_close = True
        fd.write("%s\n"%COOKIE)
        fd.write("%s:%d\n" % (H_VERSION, NATIVE_VERSION))
        fd.write("%s:%d\n" % (H_DATE_REVISION, version_number))
        attributes = ('module_num','svn_version','variable_revision_number',
                      'show_window','notes','batch_state')
        notes_idx = 4
        for module in self.modules():
            if ((modules_to_save is not None) and 
                module.module_num not in modules_to_save):
                continue
            fd.write("\n")
            attribute_values = [repr(getattr(module, attribute))
                                for attribute in attributes]
            attribute_values = [self.encode_txt(v) for v in attribute_values]
            attribute_strings = [attribute+':'+value
                                 for attribute, value 
                                 in zip(attributes, attribute_values)]
            attribute_string = '[%s]' % ('|'.join(attribute_strings))
            fd.write('%s:%s\n' % (self.encode_txt(module.module_name),
                                attribute_string))
            for setting in module.settings():
                setting_text = setting.text
                if isinstance(setting_text, unicode):
                    setting_text = setting_text.encode('utf-8')
                else:
                    setting_text = str(setting_text)
                fd.write('    %s:%s\n' % (
                    self.encode_txt(setting_text),
                    self.encode_txt(utf16encode(setting.unicode_value))))
        if needs_close:
            fd.close()
        
    def save_measurements(self, filename, measurements):
        """Save the measurements and the pipeline settings in a Matlab file
        
        filename     - name of file to create, or a file-like object
        measurements - measurements structure that is the result of running the pipeline
        """
        handles = self.build_matlab_handles()
        add_all_measurements(handles, measurements)
        handles[CURRENT][NUMBER_OF_IMAGE_SETS][0,0] = float(measurements.image_set_number+1)
        handles[CURRENT][SET_BEING_ANALYZED][0,0] = float(measurements.image_set_number+1)
        #
        # For the output file, you have to bury it a little deeper - the root has to have
        # a single field named "handles"
        #
        root = {'handles':np.ndarray((1,1),dtype=make_cell_struct_dtype(handles.keys()))}
        for key,value in handles.iteritems():
            root['handles'][key][0,0]=value
        self.savemat(filename, root)

    def write_pipeline_measurement(self, m):
        '''Write the pipeline experiment measurement to the measurements'''
        assert(isinstance(m, cpmeas.Measurements))
        fd = StringIO.StringIO()
        self.savetxt(fd)
        m.add_measurement(cpmeas.EXPERIMENT, M_PIPELINE, fd.getvalue(), 
                          can_overwrite = True)
        
    def savemat(self, filename, root):
        '''Save a handles structure accounting for scipy version compatibility to a filename or file-like object'''
        sver = scipy.__version__.split('.')
        if (len(sver) >= 2 and sver[0].isdigit() and int(sver[0]) == 0 and
            sver[1].isdigit() and int(sver[1]) < 8):
            #
            # 1-d -> 2-d not done
            #
            scipy.io.matlab.mio.savemat(filename, root, format='5',
                                        long_field_names=True)
        else:
            scipy.io.matlab.mio.savemat(filename, root, format='5',
                                        long_field_names = True, 
                                        oned_as = 'column')
    

    def build_matlab_handles(self, image_set = None, object_set = None, measurements=None):
        handles = self.save_to_handles()
        image_tools_dir = os.path.join(cpprefs.cell_profiler_root_directory(),'ImageTools')
        if os.access(image_tools_dir, os.R_OK):
            image_tools = [str(os.path.split(os.path.splitext(filename)[0])[1])
                           for filename in os.listdir(image_tools_dir)
                           if os.path.splitext(filename)[1] == '.m']
        else:
            image_tools = []
        image_tools.insert(0,'Image tools')
        npy_image_tools = np.ndarray((1,len(image_tools)),dtype=np.dtype('object'))
        for tool,idx in zip(image_tools,range(0,len(image_tools))):
            npy_image_tools[0,idx] = tool
            
        current = np.ndarray(shape=[1,1],dtype=CURRENT_DTYPE)
        handles[CURRENT]=current
        current[NUMBER_OF_IMAGE_SETS][0,0]     = [(image_set != None and image_set.legacy_fields.has_key(NUMBER_OF_IMAGE_SETS) and image_set.legacy_fields[NUMBER_OF_IMAGE_SETS]) or 1]
        current[SET_BEING_ANALYZED][0,0]       = [(measurements and measurements.image_set_number) or 1]
        current[NUMBER_OF_MODULES][0,0]        = [len(self.__modules)]
        current[SAVE_OUTPUT_HOW_OFTEN][0,0]    = [1]
        current[TIME_STARTED][0,0]             = str(datetime.datetime.now())
        current[STARTING_IMAGE_SET][0,0]       = [1]
        current[STARTUP_DIRECTORY][0,0]        = cpprefs.cell_profiler_root_directory()
        current[DEFAULT_OUTPUT_DIRECTORY][0,0] = cpprefs.get_default_output_directory()
        current[DEFAULT_IMAGE_DIRECTORY][0,0]  = cpprefs.get_default_image_directory()
        current[IMAGE_TOOLS_FILENAMES][0,0]    = npy_image_tools
        current[IMAGE_TOOL_HELP][0,0]          = []

        preferences = np.ndarray(shape=(1,1),dtype=PREFERENCES_DTYPE)
        handles[PREFERENCES] = preferences
        preferences[PIXEL_SIZE][0,0]               = cpprefs.get_pixel_size()
        preferences[DEFAULT_MODULE_DIRECTORY][0,0] = cpprefs.module_directory()
        preferences[DEFAULT_OUTPUT_DIRECTORY][0,0] = cpprefs.get_default_output_directory()
        preferences[DEFAULT_IMAGE_DIRECTORY][0,0]  = cpprefs.get_default_image_directory()
        preferences[INTENSITY_COLOR_MAP][0,0]      = 'gray'
        preferences[LABEL_COLOR_MAP][0,0]          = 'jet'
        preferences[STRIP_PIPELINE][0,0]           = 'Yes'                  # TODO - get from preferences
        preferences[SKIP_ERRORS][0,0]              = 'No'                   # TODO - get from preferences
        preferences[DISPLAY_MODE_VALUE][0,0]       = [1]                    # TODO - get from preferences
        preferences[FONT_SIZE][0,0]                = [10]                   # TODO - get from preferences
        preferences[DISPLAY_WINDOWS][0,0]          = [1 for module in self.__modules] # TODO - UI allowing user to choose whether to display a window
        
        images = {}
        if image_set:
            for provider in image_set.providers:
                image = image_set.get_image(provider.name)
                if image.image != None:
                    images[provider.name]=image.image
                if image.mask != None:
                    images['CropMask'+provider.name]=image.mask
            for key,value in image_set.legacy_fields.iteritems():
                if key != NUMBER_OF_IMAGE_SETS:
                    images[key]=value
                
        if object_set:
            for name,objects in object_set.all_objects:
                images['Segmented'+name]=objects.segmented
                if objects.has_unedited_segmented():
                    images['UneditedSegmented'+name] = objects.unedited_segmented
                if objects.has_small_removed_segmented():
                    images['SmallRemovedSegmented'+name] = objects.small_removed_segmented
                    
        if len(images):
            pipeline_dtype = make_cell_struct_dtype(images.keys())
            pipeline = np.ndarray((1,1),dtype=pipeline_dtype)
            handles[PIPELINE] = pipeline
            for name,image in images.items():
                pipeline[name][0,0] = images[name]

        no_measurements = (measurements == None or len(measurements.get_object_names())==0)
        if not no_measurements:
            measurements_dtype = make_cell_struct_dtype(measurements.get_object_names())
            npy_measurements = np.ndarray((1,1),dtype=measurements_dtype)
            handles['Measurements']=npy_measurements
            for object_name in measurements.get_object_names():
                object_dtype = make_cell_struct_dtype(measurements.get_feature_names(object_name))
                object_measurements = np.ndarray((1,1),dtype=object_dtype)
                npy_measurements[object_name][0,0] = object_measurements
                for feature_name in measurements.get_feature_names(object_name):
                    feature_measurements = np.ndarray((1,measurements.image_set_number),dtype='object')
                    object_measurements[feature_name][0,0] = feature_measurements
                    data = measurements.get_current_measurement(object_name,feature_name)
                    feature_measurements.fill(np.ndarray((0,),dtype=np.float64))
                    if data != None:
                        feature_measurements[0,measurements.image_set_number-1] = data
        return handles
    
    def find_external_input_images(self):
        '''Find the names of the images that need to be supplied externally
        
        run_external needs a dictionary of name -> image pixels with
        one name entry for every external image that must be provided.
        This function returns a list of those names.
        '''
        result = []
        for module in self.modules():
            for setting in module.settings():
                if isinstance(setting, cps.ExternalImageNameProvider):
                    result.append(setting.value)
        return result
    
    def find_external_output_images(self):
        result = []
        for module in self.modules():
            for setting in module.settings():
                if isinstance(setting, cps.ExternalImageNameSubscriber):
                    result.append(setting.value)
        return result
    
    def obfuscate(self):
        '''Tell all modules in the pipeline to obfuscate any sensitive info
        
        This call is designed to erase any information that users might
        not like to see uploaded. You should copy a pipeline before obfuscating.
        '''
        for module in self.modules():
            module.obfuscate()
        
    def restart_with_yield(self, file_name, frame=None, status_callback = None):
        '''Restart a pipeline from where we left off
        
        file_name - the name of a measurements .MAT file
        '''
        handles=scipy.io.matlab.mio.loadmat(file_name, 
                                            struct_as_record=True)
        measurements = cpmeas.Measurements()
        measurements.create_from_handles(handles)
        if handles.has_key("handles"):
            handles=handles["handles"][0,0]
        self.create_from_handles(handles)
        #
        # Redo the last image set
        #
        image_set_start = measurements.image_set_count
        #
        # Rewind the measurements to the previous image set
        #
        measurements.set_image_set_number(image_set_start)
        return self.run_with_yield(frame, 
                                   image_set_start = image_set_start, 
                                   status_callback = status_callback,
                                   initial_measurements = measurements)
        
    def run_external(self, image_dict):
        """Runs a single iteration of the pipeline with the images provided in
        image_dict and returns a dictionary mapping from image names to images 
        specified by ExternalImageNameSubscribers.
        
        image_dict - dictionary mapping image names to image pixel data in the 
                     form of a numpy array.
        """
        import cellprofiler.settings as cps
        from cellprofiler import objects as cpo

        output_image_names = self.find_external_output_images()
        input_image_names = self.find_external_input_images()
        
        # Check that the incoming dictionary matches the names expected by the
        # ExternalImageProviders
        for name in input_image_names:
            assert name in image_dict, 'Image named "%s" was not provided in the input dictionary'%(name)
        
        # Create image set from provided dict
        image_set_list = cpi.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        for image_name in input_image_names:
            input_pixels = image_dict[image_name]
            image_set.add(image_name, cpi.Image(input_pixels))
        object_set = cpo.ObjectSet()
        measurements = cpmeas.Measurements()

        # Run the modules
        for module in self.modules(): 
            workspace = cpw.Workspace(self, module, image_set, object_set, 
                                      measurements, image_set_list)
            module.run(workspace)
        
        # Populate a dictionary for output with the images to be exported
        output_dict = {}
        for name in output_image_names:
            output_dict[name] = image_set.get_image(name).pixel_data
            
        return output_dict
    
    def run(self,
            frame = None, 
            image_set_start = 1, 
            image_set_end = None,
            grouping = None,
            measurements_filename = None,
            initial_measurements = None):
        """Run the pipeline
        
        Run the pipeline, returning the measurements made
        frame - the frame to be used when displaying graphics or None to
                run headless
        image_set_start - the image number of the first image to be run
        image_set_end - the index of the last image to be run + 1
        grouping - a dictionary that gives the keys and values in the
                   grouping to run or None to run all groupings
        measurements_filename - name of file to use for measurements
        """
        measurements = cellprofiler.measurements.Measurements(
            image_set_start = image_set_start,
            filename = measurements_filename,
            copy = initial_measurements)
        measurements.is_first_image = True
        for m in self.run_with_yield(frame, image_set_start, image_set_end,
                                     grouping, 
                                     run_in_background=False,
                                     initial_measurements = measurements):
            measurements = m
        return measurements

    def run_with_yield(self,frame = None, 
                       image_set_start = 1, 
                       image_set_end = None,
                       grouping = None, run_in_background=True,
                       status_callback=None,
                       initial_measurements = None):
        """Run the pipeline, yielding periodically to keep the GUI alive.
        Yields the measurements made.
        
        Arguments:
           status_callback - None or a callable with arguments 
                             (module, image_set) that will be called before
                             running each module.
        
        Run the pipeline, returning the measurements made
        """

        def group(workspace):
            """Enumerate relevant image sets.  This function is
            side-effect free, so it can be called more than once."""
            keys, groupings = self.get_groupings(workspace)
            if grouping is not None and set(keys) != set(grouping.keys()):
                raise ValueError("The grouping keys specified on the command line (%s) must be the same as those defined by the modules in the pipeline (%s)"%(
                        ", ".join(grouping.keys()), ", ".join(keys)))
            for group_number, (grouping_keys, image_numbers) in enumerate(groupings):
                if grouping is not None and grouping != grouping_keys:
                    continue
                need_to_run_prepare_group = True
                for group_index, image_number in enumerate(image_numbers):
                    if image_number < image_set_start:
                        continue
                    if image_set_end is not None and image_number > image_set_end:
                        continue
                    if need_to_run_prepare_group:
                        yield group_number+1, group_index+1, image_number,\
                              lambda: self.prepare_group(
                                  workspace, grouping_keys, image_numbers)
                    else:
                        yield group_number+1, group_index+1, image_number, lambda: True
                    need_to_run_prepare_group = False
                if not need_to_run_prepare_group:
                    yield None, None, None, lambda workspace: self.post_group(
                        workspace, grouping_keys)

        columns = self.get_measurement_columns()
        
        if image_set_start is not None:
            assert isinstance(image_set_start, int), "Image set start must be an integer"
        if image_set_end is not None:
            assert isinstance(image_set_end, int), "Image set end must be an integer"
        if initial_measurements is None:
            measurements = cpmeas.Measurements(image_set_start)
        else:
            measurements = initial_measurements
            
        image_set_list = cpi.ImageSetList()
        workspace = cpw.Workspace(self, None, None, None,
                                  measurements, image_set_list, frame)

        try:
            if not self.prepare_run(workspace):
                return
            #
            # Remove image sets outside of the requested ranges
            #
            image_numbers = measurements.get_image_numbers()
            to_remove = []
            if image_set_start is not None:
                to_remove += [x for x in image_numbers
                              if x < image_set_start]
                image_numbers = [x for x in image_numbers 
                                 if x >= image_set_start]
            if image_set_end is not None:
                to_remove += [x for x in image_numbers
                              if x > image_set_end]
                image_numbers = [x for x in image_numbers
                                 if x <= image_set_end]
            if grouping is not None:
                keys, groupings = self.get_groupings(workspace)
                for grouping_keys, grouping_image_numbers in groupings:
                    if grouping_keys != grouping:
                        to_remove += list(grouping_image_numbers)
            if (len(to_remove) > 0 and 
                measurements.has_feature(cpmeas.IMAGE, cpmeas.IMAGE_NUMBER)):
                for image_number in np.unique(to_remove):
                    measurements.remove_measurement(
                        cpmeas.IMAGE, cpmeas.IMAGE_NUMBER, image_number)

            # Keep track of progress for the benefit of the progress window.
            num_image_sets = len(measurements.get_image_numbers())
            image_set_count = -1
            is_first_image_set = True
            last_image_number = None
            pipeline_stats_logger.info("Times reported are CPU times for each module, not wall-clock time")
            for group_number, group_index, image_number, closure \
                in group(workspace):
                if image_number is None:
                    if not closure(workspace):
                        measurements.add_experiment_measurement(EXIT_STATUS,
                                                                "Failure")
                        return
                    continue
                image_set_count += 1
                if not closure():
                    return
                if last_image_number is not None:
                    image_set_list.purge_image_set(last_image_number-1)
                last_image_number = image_number
                measurements.next_image_set(image_number)
                if is_first_image_set:
                    measurements.image_set_start = image_number
                    measurements.is_first_image = True
                    is_first_image_set = False
                measurements.group_number = group_number
                measurements.group_index = group_index
                numberof_windows = 0;
                slot_number = 0
                object_set = cpo.ObjectSet()
                image_set = image_set_list.get_image_set(image_number-1)
                outlines = {}
                should_write_measurements = True
                grids = None
                for module in self.modules():
                    gc.collect()
                    if module.should_stop_writing_measurements():
                        should_write_measurements = False
                    else:
                        module_error_measurement = ('ModuleError_%02d%s' %
                                                    (module.module_num,
                                                     module.module_name))
                        execution_time_measurement = ('ExecutionTime_%02d%s' %
                                                      (module.module_num,
                                                       module.module_name))
                    failure = 1
                    exception = None
                    tb = None
                    frame_if_shown = frame if module.show_window else None
                    workspace = cpw.Workspace(self,
                                              module,
                                              image_set,
                                              object_set,
                                              measurements,
                                              image_set_list,
                                              frame_if_shown,
                                              outlines = outlines)
                    grids = workspace.set_grids(grids)
                    if status_callback:
                        status_callback(module, len(self.modules()), 
                                        image_set_count, num_image_sets)
                    start_time = datetime.datetime.now()
                    t0 = sum(os.times()[:-1])
                    if not run_in_background:
                        try:
                            module.run(workspace)
                        except Exception, instance:
                            logger.error(
                                "Error detected during run of module %s",
                                module.module_name, exc_info=True)
                            exception = instance
                            tb = sys.exc_traceback
                        yield measurements
                    elif module.is_interactive():
                        worker = ModuleRunner(module, workspace, frame)
                        worker.run()
                        if worker.exception is not None:
                            exception = worker.exception
                            tb = worker.tb
                        yield measurements
                    else:
                        # Turn on checks for calls to create_or_find_figure() in workspace.
                        workspace.in_background = True
                        worker = ModuleRunner(module, workspace, frame)
                        worker.start()
                        yield measurements
                        # After the worker finishes, we can clear this flag.
                        workspace.in_background = False
                        if worker.exception is not None:
                            exception = worker.exception
                            tb = worker.tb
                    t1 = sum(os.times()[:-1])
                    delta_sec = max(0,t1-t0)
                    pipeline_stats_logger.info(
                        "%s: Image # %d, module %s # %d: %.2f sec%s" %
                        (start_time.ctime(), image_number, 
                         module.module_name, module.module_num, 
                         delta_sec,
                         "" if module.is_interactive() else " (bg)"))
                    if ((workspace.frame is not None) and
                        (exception is None)):
                        try:
                            module.display(workspace)
                        except Exception, instance:
                            logger.error("Failed to display results for module %s",
                                         module.module_name, exc_info=True)
                            exception = instance
                    workspace.refresh()
                    failure = 0
                    if exception is not None:
                        event = RunExceptionEvent(exception,module, tb)
                        self.notify_listeners(event)
                        if event.cancel_run:
                            return
                        elif event.skip_thisset:
                            #Skip this image, continue to others
                            workspace.set_disposition(cpw.DISPOSITION_SKIP)
                            should_write_measurements = False
                            measurements = None

                    # Paradox: ExportToDatabase must write these columns in order 
                    #  to complete, but in order to do so, the module needs to 
                    #  have already completed. So we don't report them for it.
                    if (module.module_name != 'Restart' and 
                        should_write_measurements):
                        measurements.add_measurement('Image',
                                                     module_error_measurement,
                                                     np.array([failure]));
                        measurements.add_measurement('Image',
                                                     execution_time_measurement,
                                                     np.array([delta_sec]))
                    while (workspace.disposition == cpw.DISPOSITION_PAUSE and
                           frame is not None):
                        # try to leave measurements temporary file in a readable state
                        measurements.flush()
                        yield measurements
                    if workspace.disposition == cpw.DISPOSITION_SKIP:
                        break
                    elif workspace.disposition == cpw.DISPOSITION_CANCEL:
                        measurements.add_experiment_measurement(EXIT_STATUS,
                                                                "Failure")
                        return

            if measurements is not None:
                exit_status = self.post_run(measurements, image_set_list, frame)
                #
                # Record the status after post_run
                #
                measurements.add_experiment_measurement(EXIT_STATUS, exit_status)
        finally:
            if measurements is not None:
                 # XXX - We want to force the measurements to update the
                 # underlying file, or else we get partially written HDF5
                 # files.  There must be a better way to do this.
                measurements.flush()
                del measurements
            self.end_run()

    def end_run(self):
        '''Tell everyone that a run is ending'''
        self.notify_listeners(EndRunEvent())
        
    def run_group_with_yield(self, workspace, grouping, image_numbers, 
                             stop_module, title, message):
        '''Run the modules for the image_numbers in a group up to an agg module
        
        This method runs a pipeline up to an aggregation step on behalf of
        an aggregation module. At present, you can call this within
        prepare_group to collect the images needed for aggregation.
        
        workspace - workspace containing the pipeline, image_set_list and
        measurements.
        
        grouping - the grouping dictionary passed into prepare_group.
        
        image_numbers - the image numbers that comprise the group
        
        stop_module - the aggregation module to stop at.
        
        The function yields the current workspace at the end of processing
        each image set. The workspace has a valid image_set and the 
        measurements' image_number is the current image number.
        '''
        m = workspace.measurements
        pipeline = workspace.pipeline
        image_set_list = workspace.image_set_list
        orig_image_number = m.image_set_number
        if not pipeline.in_batch_mode() and not cpprefs.get_headless():
            import wx
            progress_dialog = wx.ProgressDialog(
                title, message,
                style = wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)
        else:
            progress_dialog = None
        
        try:
            for i, image_number in enumerate(image_numbers):
                m.image_set_number = image_number
                image_set = image_set_list.get_image_set(image_number-1)
                assert isinstance(image_set, cpi.ImageSet)
                object_set = cpo.ObjectSet()
                old_providers = list(image_set.providers)
                for module in pipeline.modules():
                    w = cpw.Workspace(self, module, image_set, object_set, m, 
                                      image_set_list)
                    if module == stop_module:
                        yield w
                        # Reset state of image set
                        del image_set.providers[:]
                        image_set.providers.extend(old_providers)
                        break
                    else:
                        module.run(w)
                    if progress_dialog is not None:
                        should_continue, skip = progress_dialog.Update(i+1)
                        if not should_continue:
                            progress_dialog.EndModal(0)
                            return
        finally:
            if progress_dialog is not None:
                progress_dialog.Destroy()
            m.image_set_number = orig_image_number
        
    def prepare_run(self, workspace):
        """Do "prepare_run" on each module to initialize the image_set_list
        
        workspace - workspace for the run
        
             pipeline - this pipeline
             
             image_set_list - the image set list for the run. The modules
                              should set this up with the image sets they need.
                              The caller can set test mode and
                              "combine_path_and_file" on the image set before
                              the call.
                              
             measurements - the modules should record URL information here
             
             frame - the CPFigureFrame if not headless
             
             Returns True if all modules succeeded, False if any module reported
             failure or threw an exception
             
        test_mode - None = use pipeline's test mode, True or False to set explicitly
        """
        assert(isinstance(workspace, cpw.Workspace))
        m = workspace.measurements
        self.write_pipeline_measurement(m)

        for module in self.modules():
            try:
                workspace.set_module(module)
                workspace.show_frame(module.show_window)
                if not module.prepare_run(workspace):
                    return False
            except Exception,instance:
                logging.error("Failed to prepare run for module %s",
                              module.module_name, exc_info=True)
                event = RunExceptionEvent(instance, module, sys.exc_info()[2])
                self.notify_listeners(event)
                if event.cancel_run:
                    return False
        assert not any([len(workspace.image_set_list.get_image_set(i).providers)
                        for i in range(workspace.image_set_list.count())]),\
               "Image providers cannot be added in prepare_run. Please add them in prepare_group instead"
        return True
    
    def post_run(self, measurements, image_set_list, frame):
        """Do "post_run" on each module to perform aggregation tasks
        
        measurements - the measurements for the run
        image_set_list - the image set list for the run
        frame - the topmost frame window or None if no GUI
        """
        for module in self.modules():
            workspace = cpw.Workspace(self,
                                      module,
                                      None,
                                      None,
                                      measurements,
                                      image_set_list,
                                      frame if module.show_window else None)
            workspace.refresh()
            try:
                module.post_run(workspace)
            except Exception, instance:
                logging.error(
                    "Failed to complete post_run processing for module %s.",
                    module.module_name, exc_info=True)
                event = RunExceptionEvent(instance, module, sys.exc_info()[2])
                self.notify_listeners(event)
                if event.cancel_run:
                    return "Failure"
        return "Complete"
    
    def prepare_to_create_batch(self, workspace, fn_alter_path):
        '''Prepare to create a batch file
        
        This function is called when CellProfiler is about to create a
        file for batch processing. It will pickle the image set list's
        "legacy_fields" dictionary. This callback lets a module prepare for
        saving.
        
        workspace - the workspace to be saved
        fn_alter_path - this is a function that takes a pathname on the local
                        host and returns a pathname on the remote host. It
                        handles issues such as replacing backslashes and
                        mapping mountpoints. It should be called for every
                        pathname stored in the settings or legacy fields.
        '''
        assert workspace.pipeline == self
        for module in self.modules():
            try:
                workspace.set_module(module)
                module.prepare_to_create_batch(workspace, 
                                               fn_alter_path)
            except Exception, instance:
                logger.error("Failed to collect batch information for module %s",
                             module.module_name, exc_info=True)
                event = RunExceptionEvent(instance, module, sys.exc_info()[2])
                self.notify_listeners(event)
                if event.cancel_run:
                    return
    
    def get_groupings(self, workspace):
        '''Return the image groupings of the image sets in an image set list
        
        returns a tuple of key_names and group_list:
        key_names - the names of the keys that identify the groupings
        group_list - a sequence composed of two-tuples.
                     the first element of the tuple has the values for
                     the key_names for this group.
                     the second element of the tuple is a sequence of
                     image numbers comprising the image sets of the group
        For instance, an experiment might have key_names of 'Metadata_Row'
        and 'Metadata_Column' and a group_list of:
        [ (('A','01'), [0,96,192]),
          (('A','02'), [1,97,193]),... ]
        '''
        groupings = None
        grouping_module = None
        for module in self.modules():
            workspace.set_module(module)
            new_groupings = module.get_groupings(workspace)
            if new_groupings is None:
                continue
            if groupings is None:
                groupings = new_groupings
                grouping_module = module
            else:
                raise ValueError("The pipeline has two grouping modules: # %d "
                                 "(%s) and # %d (%s)" %
                                 (grouping_module.module_num, 
                                  grouping_module.module_name,
                                  module.module_num,
                                  module.module_name))
        if groupings is None:
            return ((), (((),workspace.measurements.get_image_numbers()),))
        return groupings
    
    def get_undefined_metadata_tags(self, pattern):
        """Find metadata tags not defined within the current measurements
        
        pattern - a regexp-like pattern that specifies how to insert
                  metadata into a string. Each token has the form:
                  "\(?<METADATA_TAG>\)" (matlab-style) or
                  "\g<METADATA_TAG>" (Python-style)
        """
        columns = self.get_measurement_columns()
        current_metadata = []
        for column in columns:
            object_name, feature, coltype = column[:3]
            if (object_name == cpmeas.IMAGE and feature.startswith(cpmeas.C_METADATA)):
                current_metadata.append(feature[(len(cpmeas.C_METADATA)+1):])
            
        m = re.findall('\\(\\?[<](.+?)[>]\\)', pattern)
        if not m:
            m = re.findall('\\\\g[<](.+?)[>]', pattern)
        if m:
            undefined_tags = list(set(m).difference(current_metadata))
            return undefined_tags
        else:
            return []
                
    def prepare_group(self, workspace, grouping, image_numbers):
        '''Prepare to start processing a new group
        
        workspace - the workspace containing the measurements and image set list
        grouping - a dictionary giving the keys and values for the group
        
        returns true if the group should be run
        '''
        #
        # Clean the image set providers (can be filled in if run in
        # an unconventional manner, e.g. debug mode)
        #
        image_set_list = workspace.image_set_list
        for image_number in image_numbers:
            image_set = image_set_list.get_image_set(image_number -1)
            del image_set.providers[:]
            
        for module in self.modules():
            try:
                module.prepare_group(workspace, grouping, image_numbers)
            except Exception, instance:
                logger.error("Failed to prepare group in module %s",
                             module.module_name, exc_info=True)
                event = RunExceptionEvent(instance, module, sys.exc_info()[2])
                self.notify_listeners(event)
                if event.cancel_run:
                    return False
        return True
    
    def post_group(self, workspace, grouping):
        '''Do post-processing after a group completes
        
        workspace - the last workspace run
        '''
        for module in self.modules():
            try:
                module.post_group(workspace, grouping)
            except Exception, instance:
                logging.error(
                    "Failed during post-group processing for module %s",
                    module.module_name, exc_info=True)
                event = RunExceptionEvent(instance, module, sys.exc_info()[2])
                self.notify_listeners(event)
                if event.cancel_run:
                    return False
        return True
    
    def in_batch_mode(self):
        '''Return True if the pipeline is in batch mode'''
        for module in self.modules():
            batch_mode = module.in_batch_mode()
            if batch_mode is not None:
                return batch_mode
            
    def turn_off_batch_mode(self):
        '''Reset the pipeline to an editable state if batch mode is on
        
        A module is allowed to create hidden information that it uses
        to turn batch mode on or to save state to be used in batch mode.
        This call signals that the pipeline has been opened for editing,
        even if it is a batch pipeline; all modules should be restored
        to a state that's appropriate for creating a batch file, not
        for running a batch file.
        '''
        for module in self.modules():
            module.turn_off_batch_mode()

    def get_test_mode(self):
        return self.__test_mode
    def set_test_mode(self, val):
        self.__test_mode = val
    test_mode = property(get_test_mode, set_test_mode)
    

    def clear(self):
        old_modules = self.__modules
        def undo():
            for module in old_modules:
                self.add_module(module)
        self.__undo_stack.append((undo, 
                                  "Undo clear"))
        self.__modules = []
        self.notify_listeners(PipelineClearedEvent())
    
    def move_module(self,module_num,direction):
        """Move module # ModuleNum either DIRECTION_UP or DIRECTION_DOWN in the list
        
        Move the 1-indexed module either up one or down one in the list, displacing
        the other modules in the list
        """
        idx=module_num-1
        if direction == DIRECTION_DOWN:
            if module_num >= len(self.__modules):
                raise ValueError('%(module_num)d is at or after the last module in the pipeline and can''t move down'%(locals()))
            module = self.__modules[idx]
            new_module_num = module_num+1
            module.set_module_num(module_num+1)
            next_module = self.__modules[idx+1]
            next_module.set_module_num(module_num)
            self.__modules[idx]=next_module
            self.__modules[idx+1]=module
            next_settings = self.__settings[idx+1]
            self.__settings[idx+1] = self.__settings[idx]
            self.__settings[idx] = next_settings
        elif direction == DIRECTION_UP:
            if module_num <= 1:
                raise ValueError('The module is at the top of the pipeline and can''t move up')
            module = self.__modules[idx]
            prev_module = self.__modules[idx-1]
            new_module_num = prev_module.module_num
            module.module_num = new_module_num
            prev_module.module_num = module_num
            self.__modules[idx]=self.__modules[idx-1]
            self.__modules[idx-1]=module
            prev_settings = self.__settings[idx-1]
            self.__settings[idx-1] = self.__settings[idx]
            self.__settings[idx] = prev_settings
        else:
            raise ValueError('Unknown direction: %s'%(direction))    
        self.notify_listeners(ModuleMovedPipelineEvent(new_module_num,direction))
        def undo():
            self.move_module(module.module_num, 
                             DIRECTION_DOWN if direction == DIRECTION_UP
                             else DIRECTION_UP)
        message = "Move %s %s" % (module.module_name, direction)
        self.__undo_stack.append((undo, message))
    
    def has_undo(self):
        '''True if an undo action can be performed'''
        return len(self.__undo_stack)
    
    def undo(self):
        '''Undo the last action'''
        if len(self.__undo_stack):
            action = self.__undo_stack.pop()[0]
            real_undo_stack = self.__undo_stack
            self.__undo_stack = []
            try:
                action()
            finally:
                self.__undo_stack = real_undo_stack
            
    def undo_action(self):
        '''A user-interpretable string telling the user what the action was'''
        if len(self.__undo_stack) == 0:
            return "Nothing to undo"
        return self.__undo_stack[-1][1]
    
    def start_undoable_action(self):
        '''Start editing the pipeline
        
        This marks a start of a series of actions which will be undone
        all at once.
        '''
        self.__undo_start = len(self.__undo_stack)
        
    def stop_undoable_action(self, name = "Composite edit"):
        '''Stop editing the pipeline, combining many actions into one'''
        if len(self.__undo_stack) > self.__undo_start+1:
            # Only combine if two or more edits
            actions = self.__undo_stack[self.__undo_start:]
            del self.__undo_stack[self.__undo_start:]
            def undo():
                for action, message in reversed(actions):
                    action()
            self.__undo_stack.append((undo, name))
            
    def modules(self):
        return self.__modules
    
    def module(self,module_num):
        module = self.__modules[module_num-1]
        assert module.module_num==module_num,'Misnumbered module. Expected %d, got %d'%(module_num,module.module_num)
        return module
    
    def add_module(self,new_module):
        """Insert a module into the pipeline with the given module #
        
        Insert a module into the pipeline with the given module #. 
        'file_name' - the path to the file containing the variables for the module.
        ModuleNum - the one-based index for the placement of the module in the pipeline
        """
        module_num = new_module.module_num
        idx = module_num-1
        self.__modules = self.__modules[:idx]+[new_module]+self.__modules[idx:]
        for module,mn in zip(self.__modules[idx+1:],range(module_num+1,len(self.__modules)+1)):
            module.module_num = mn
        self.notify_listeners(ModuleAddedPipelineEvent(module_num))
        self.__settings.insert(idx, [str(setting) 
                                     for setting in new_module.settings()])
        def undo():
            self.remove_module(new_module.module_num)
        self.__undo_stack.append((undo, 
                                  "Add %s module" % new_module.module_name))
    
    def remove_module(self,module_num):
        """Remove a module from the pipeline
        
        Remove a module from the pipeline
        ModuleNum - the one-based index of the module
        """
        idx =module_num-1
        removed_module = self.__modules[idx]
        self.__modules = self.__modules[:idx]+self.__modules[idx+1:]
        for module in self.__modules[idx:]:
            module.module_num = module.module_num-1
        self.notify_listeners(ModuleRemovedPipelineEvent(module_num))
        del self.__settings[idx]
        def undo():
            self.add_module(removed_module)
        self.__undo_stack.append((undo, "Remove %s module" %
                                  removed_module.module_name))
    
    def edit_module(self, module_num):
        """Notify listeners of a module edit
        
        """
        idx = module_num - 1
        old_settings = self.__settings[idx]
        module = self.modules()[idx]
        new_settings = [str(setting) for setting in module.settings()]
        self.notify_listeners(ModuleEditedPipelineEvent(module_num))
        self.__settings[idx] = new_settings
        variable_revision_number = module.variable_revision_number
        module_name = module.module_name
        def undo():
            module = self.modules()[idx]
            module.set_settings_from_values(old_settings,
                                            variable_revision_number,
                                            module_name, False)
            self.notify_listeners(ModuleEditedPipelineEvent(module_num))
            self.__settings[idx] = old_settings
        self.__undo_stack.append((undo, "Edited %s" % module_name))
    
    def test_valid(self):
        """Throw a ValidationError if the pipeline isn't valid
        
        """
        for module in self.__modules:
            module.test_valid(self)
    
    def notify_listeners(self,event):
        """Notify listeners of an event that happened to this pipeline
        
        """
        for listener in self.__listeners:
            listener(self,event)
    
    def add_listener(self,listener):
        self.__listeners.append(listener)
        
    def remove_listener(self,listener):
        self.__listeners.remove(listener)

    def is_image_from_file(self, image_name):
        """Return True if any module in the pipeline claims to be
        loading this image name from a file."""
        for module in self.modules():
            if module.is_image_from_file(image_name):
                return True
        return False
    
    def get_measurement_columns(self, terminating_module=None):
        '''Return a sequence describing the measurement columns for this pipeline
        
        This call returns one element per image or object measurement
        made by each module during image set analysis. The element itself
        is a 3-tuple:
        first entry: either one of the predefined measurement categories,
                     {Image", "Experiment" or "Neighbors" or the name of one
                     of the objects.
        second entry: the measurement name (as would be used in a call 
                      to add_measurement)
        third entry: the column data type (for instance, "varchar(255)" or
                     "float")
        fourth entry (optional): attribute dictionary. This tags
                     the column with attributes such as MCA_AVAILABLE_POST_GROUP
                     (column values are only added in post_group).
        '''
        hash =  self.settings_hash()
        if hash != self.__measurement_column_hash:
            self.__measurement_columns = {}
            self.__measurement_column_hash = hash
        
        terminating_module_num = ((len(self.modules())+1) 
                                  if terminating_module == None
                                  else terminating_module.module_num)
        if self.__measurement_columns.has_key(terminating_module_num):
            return self.__measurement_columns[terminating_module_num]
        columns = [
            (cpmeas.EXPERIMENT, M_PIPELINE, cpmeas.COLTYPE_LONGBLOB),
            (cpmeas.IMAGE, GROUP_NUMBER, cpmeas.COLTYPE_INTEGER),
            (cpmeas.IMAGE, GROUP_INDEX, cpmeas.COLTYPE_INTEGER)]
        should_write_columns = True
        for module in self.modules():
            if (terminating_module is not None and 
                terminating_module_num == module.module_num):
                break
            columns += module.get_measurement_columns(self)
            if module.should_stop_writing_measurements():
                should_write_columns = False
            if should_write_columns:
                module_error_measurement = 'ModuleError_%02d%s'%(module.module_num,module.module_name)
                execution_time_measurement = 'ExecutionTime_%02d%s'%(module.module_num,module.module_name)
                columns += [(cpmeas.IMAGE, module_error_measurement, cpmeas.COLTYPE_INTEGER),
                            (cpmeas.IMAGE, execution_time_measurement, cpmeas.COLTYPE_INTEGER)]
        self.__measurement_columns[terminating_module_num] = columns
        return columns
    
    def get_provider_dictionary(self, groupname, module = None):
        '''Get a dictionary of all providers for a given category
        
        groupname - the name of the category from cellprofiler.settings:
            IMAGE_GROUP for image providers, OBJECT_GROUP for object providers
            or MEASUREMENTS_GROUP for measurement providers.
            
        module - the module that will subscribe to the names. If None, all
        providers are listed, if a module, only the providers for that module's
        place in the pipeline are listed.
            
        returns a dictionary where the key is the name and the value is
        a list of tuples of module and setting where the module provides
        the name and the setting is the setting that controls the name (and
        the setting can be None).
        
        '''
        target_module = module
        result = {}
        #
        # Walk through the modules to find subscriber and provider settings
        #
        for module in self.modules():
            if (target_module is not None and 
                target_module.module_num <= module.module_num):
                break
            #
            # Find "other_providers" - providers that aren't specified
            # by single settings.
            #
            p = module.other_providers(groupname)
            for name in p:
                if (not result.has_key(name)) or target_module is not None:
                    result[name] = []
                result[name].append((module, None))
            if groupname == cps.MEASUREMENTS_GROUP:
                for c in module.get_measurement_columns(self):
                    object_name, feature_name = c[:2]
                    k = (object_name, feature_name)
                    if (not result.has_key(k)) or target_module is not None:
                        result[k] = []
                    result[k].append((module, None))
            for setting in module.visible_settings():
                if (isinstance(setting, cps.NameProvider) and
                    setting.get_group() == groupname):
                    name = setting.value
                    if name == cps.DO_NOT_USE:
                        continue
                    if not result.has_key(name) or target_module is not None:
                        result[name] = []
                    result[name].append((module, setting))
        return result
    
    def get_dependency_graph(self):
        '''Create a graph that describes the producers and consumers of objects
        
        returns a list of Dependency objects. These can be used to create a
        directed graph that describes object and image dependencies.
        '''
        #
        # These dictionaries have the following structure:
        # * top level dictionary key indicates whether it is an object, image
        #   or measurement dependency
        # * second level dictionary key is the name of the object or image or
        #   a tuple of (object_name, feature) for a measurement.
        # * the value of the second-level dictionary is a list of tuples
        #   where the first element of the tuple is the module and the
        #   second is either None or the setting.
        #
        all_groups = (cps.OBJECT_GROUP, cps.IMAGE_GROUP, cps.MEASUREMENTS_GROUP)
        providers = dict([(g, self.get_provider_dictionary(g))
                          for g in all_groups])
        #
        # Now match subscribers against providers.
        #
        result = []
        for module in self.modules():
            for setting in module.visible_settings():
                if isinstance(setting, cps.NameSubscriber):
                    group = setting.get_group()
                    name = setting.value
                    if (providers.has_key(group) and 
                        providers[group].has_key(name)):
                        for pmodule, psetting in providers[group][name]:
                            if pmodule.module_num < module.module_num:
                                if group == cps.OBJECT_GROUP:
                                    dependency = ObjectDependency(
                                        pmodule, module, name,
                                        psetting, setting)
                                    result.append(dependency)
                                elif group == cps.IMAGE_GROUP:
                                    dependency = ImageDependency(
                                        pmodule, module, name,
                                        psetting, setting)
                                    result.append(dependency)
                                break
                elif isinstance(setting, cps.Measurement):
                    object_name = setting.get_measurement_object()
                    feature_name = setting.value
                    key = (object_name, feature_name)
                    if providers[cps.MEASUREMENTS_GROUP].has_key(key):
                        for pmodule, psetting in providers[cps.MEASUREMENTS_GROUP][key]:
                            if pmodule.module_num < module.module_num:
                                dependency = MeasurementDependency(
                                    pmodule, module, object_name, feature_name,
                                    psetting, setting)
                                result.append(dependency)
                                break
        return result
    
    def synthesize_measurement_name(self, module, object, category, 
                                    feature, image, scale):
        '''Turn a measurement requested by a Matlab module into a measurement name
        
        Some Matlab modules specify measurement names as a combination
        of category, feature, image name and scale, but not all measurements
        have associated images or scales. This function attempts to match
        the given parts to the measurements available to the module and
        returns the best guess at a measurement. It throws a value error
        exception if it can't find a match
        
        module - the module requesting the measurement. Only measurements
                 made prior to this module will be considered.
        object - the object name or "Image"
        category - The module's measurement category (e.g. Intensity or AreaShape)
        feature - a descriptive name for the measurement
        image - the measurement should be made on this image (optional)
        scale - the measurement should be made at this scale
        '''
        measurement_columns = self.get_measurement_columns(module)
        measurements = [x[1] for x in measurement_columns
                        if x[0] == object]
        for measurement in ("_".join((category,feature,image,scale)),
                            "_".join((category,feature,image)),
                            "_".join((category,feature,scale)),
                            "_".join((category,feature))):
            if measurement in measurements:
                return measurement
        raise ValueError("No such measurement in pipeline: " +
                         ("Category = %s" % category) +
                         (", Feature = %s" % feature) +
                         (", Image (optional) = %s" % image) +
                         (", Scale (optional) = %s" % scale))
        
class AbstractPipelineEvent:
    """Something that happened to the pipeline and was indicated to the listeners
    """
    def event_type(self):
        raise NotImplementedError("AbstractPipelineEvent does not implement an event type")

class PipelineLoadedEvent(AbstractPipelineEvent):
    """Indicates that the pipeline has been (re)loaded
    
    """
    def event_type(self):
        return "PipelineLoaded"

class PipelineClearedEvent(AbstractPipelineEvent):
    """Indicates that all modules have been removed from the pipeline
    
    """
    def event_type(self):
        return "PipelineCleared"

DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
class ModuleMovedPipelineEvent(AbstractPipelineEvent):
    """A module moved up or down
    
    """
    def __init__(self,module_num, direction):
        self.module_num = module_num
        self.direction = direction
    
    def event_type(self):
        return "Module moved"

class ModuleAddedPipelineEvent(AbstractPipelineEvent):
    """A module was added to the pipeline
    
    """
    def __init__(self,module_num):
        self.module_num = module_num
    
    def event_type(self):
        return "Module Added"
    
class ModuleRemovedPipelineEvent(AbstractPipelineEvent):
    """A module was removed from the pipeline
    
    """
    def __init__(self,module_num):
        self.module_num = module_num
        
    def event_type(self):
        return "Module deleted"

class ModuleEditedPipelineEvent(AbstractPipelineEvent):
    """A module had its settings changed
    
    """
    def __init__(self, module_num):
        self.module_num = module_num
    
    def event_type(self):
        return "Module edited"

class RunExceptionEvent(AbstractPipelineEvent):
    """An exception was caught during a pipeline run
    
    Initializer:
    error - exception that was thrown
    module - module that was executing
    tb - traceback at time of exception, e.g from sys.exc_info
    """
    def __init__(self, error, module, tb = None):
        self.error     = error
        self.cancel_run = True
        self.skip_thisset = False
        self.module    = module
        self.tb = tb
    
    def event_type(self):
        return "Pipeline run exception"

class LoadExceptionEvent(AbstractPipelineEvent):
    """An exception was caught during pipeline loading
    
    """
    def __init__(self, error, module, module_name = None, settings = None):
        self.error     = error
        self.cancel_run = True
        self.module    = module
        self.module_name = module_name
        self.settings = settings
    
    def event_type(self):
        return "Pipeline load exception"
    
class EndRunEvent(AbstractPipelineEvent):
    """A run ended"""
    def event_type(self):
        return "Run ended"

class Dependency(object):
    '''This class documents the dependency of one module on another
    
    A module is dependent on another if the dependent module requires
    data from the producer module. That data can be objects (label matrices),
    a derived image or measurements.
    '''
    def __init__(self, source_module, destination_module, 
                 source_setting = None, destination_setting = None):
        '''Constructor
        
        source_module - the module that produces the data
        destination_module - the module that uses the data
        source_setting - the module setting that names the item (can be None)
        destination_setting - the module setting in the destination that
        picks the setting
        '''
        self.__source_module = source_module
        self.__destination_module = destination_module
        self.__source_setting = source_setting
        self.__destination_setting = destination_setting
        
    @property
    def source(self):
        '''The source of the data item'''
        return self.__source_module
    
    @property
    def source_setting(self):
        '''The setting that names the data item
        
        This can be None if it's ambiguous.
        '''
        return self.__source_setting

    @property
    def destination(self):
        '''The user of the data item'''
        return self.__destination_module
    
    @property
    def destination_setting(self):
        '''The setting that picks the data item
        
        This can be None if it's ambiguous.
        '''
        return self.__destination_setting
    
class ObjectDependency(Dependency):
    '''A dependency on an object labeling'''
    def __init__(self, source_module, destination_module, object_name,
                 source_setting = None, destination_setting = None):
        super(type(self), self).__init__(source_module, destination_module,
                                         source_setting, destination_setting)
        self.__object_name = object_name
        
    @property
    def object_name(self):
        '''The name of the objects produced by the source and used by the dest'''
        return self.__object_name
    
    def __str__(self):
        return "Object: %s" % self.object_name

class ImageDependency(Dependency):
    '''A dependency on an image'''
    def __init__(self, source_module, destination_module, image_name,
                 source_setting = None, destination_setting = None):
        super(type(self), self).__init__(source_module, destination_module,
                                         source_setting, destination_setting)
        self.__image_name = image_name
        
    @property
    def image_name(self):
        '''The name of the image produced by the source and used by the dest'''
        return self.__image_name

    def __str__(self):
        return "Image: %s" % self.image_name
    
class MeasurementDependency(Dependency):
    '''A dependency on a measurement'''
    def __init__(self, source_module, destination_module, object_name,
                 feature, source_setting = None, destination_setting = None):
        '''Initialize using source, destination and measurement
        
        source_module - module producing the measurement
        
        destination_module - module using the measurement
        
        object_name - the measurement is made on the objects with this name
        (or Image for image measurements)
        
        feature - the feature name for the measurement, for instance AreaShape_Area
        
        source_setting - the module setting that controls production of this
        measurement (very typically = None for no such thing)
        
        destination_setting - the module setting that chooses the measurement
        for the user of the data, for instance a MeasurementSetting
        '''
        super(type(self), self).__init__(source_module, destination_module,
                                         source_setting, destination_setting)
        self.__object_name = object_name
        self.__feature = feature
        
    @property
    def object_name(self):
        '''The objects / labels used when producing the measurement'''
        return self.__object_name
    
    @property
    def feature(self):
        '''The name of the measurement'''
        return self.__feature

    def __str__(self):
        return "Measurement: %s.%s" % (self.object_name, self.feature)

