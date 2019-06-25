import sys
sys.path.insert(0, '/home/forrestli/ITK/build/Wrapping/Generators/Python')
sys.path.insert(1, '/home/forrestli/ITK/build/lib')
sys.path.insert(2, '/home/forrestli/ITKTubeTK/build2/lib')

import itk
import random
import numpy as np

from helper2 import Api, rpc

def generate_tube_colormap(group):
    colormap = {}
    children = group.GetChildren(1) # recursive
    for idx in range(len(children)):
        child = itk.down_cast(children[idx])
        colormap[child.GetId()] = [c * 255 for c in child.GetProperty().GetColor()]

    return colormap

class SegmentApi(Api):
    def __init__(self):
        super().__init__()
        self.segmenter = None
        self.input_image = None
        self.next_tube_id = 1
        self.tube_id_mapping = {}
        self.tube_image = None

    def get_labelmap(self, tube):
        if self.input_image is None:
            raise Exception('No input image?????')

        f = itk.SpatialObjectToImageFilter[itk.SpatialObject[3], itk.Image[itk.UC, 3]].New()

        # same origin and spacing and dir as input_image
        f.SetOrigin(self.input_image.GetOrigin())
        f.SetSpacing(self.input_image.GetSpacing())
        f.SetDirection(self.input_image.GetDirection())
        f.SetSize(self.input_image.GetLargestPossibleRegion().GetSize())

        f.SetUseObjectValue(False)
        f.SetOutsideValue(0)
        f.SetInsideValue(1)

        f.SetInput(tube)
        f.Update()

        mask = f.GetOutput()
        voxels = itk.GetArrayFromImage(mask)

        padded = np.concatenate(([0], voxels.flatten(), [0]))
        run_edges = np.diff(padded)
        run_starts, = np.where(run_edges > 0)
        run_stops, = np.where(run_edges < 0)
        run_lengths = run_stops - run_starts
        return np.array(list(zip(run_starts, run_lengths)), dtype='uint32').flatten()

    @rpc('preprocess')
    def preprocess(self, image, filters):
        filters = {f['filter']:f for f in filters}

        OldImageType = type(image)
        ImageType = itk.Image[itk.F, 3]
        image = itk.CastImageFilter[OldImageType, itk.Image[itk.F, 3]].New()(image)

        result = image
        if 'windowLevel' in filters:
            args = filters['windowLevel']
            wl_filter = itk.IntensityWindowingImageFilter[ImageType, ImageType].New()
            wl_filter.SetInput(image)
            wl_filter.SetWindowLevel(args['width'], args['level'])
            wl_filter.SetOutputMinimum(0)
            wl_filter.SetOutputMaximum(1024)
            wl_filter.Update()
            result = wl_filter.GetOutput()

        if 'median' in filters:
            args = filters['median']
            median_filter = itk.MedianImageFilter[ImageType, ImageType].New()
            median_filter.SetInput(image)
            median_filter.SetRadius(args['radius'])
            median_filter.Update()
            result = median_filter.GetOutput()

        result = itk.CastImageFilter[ImageType, OldImageType].New()(result)

        self.persist(result)
        return result

    @rpc('set_segment_image')
    def set_segment_image(self, image):
        if image != self.input_image:
            self.input_image = image
            self.segmenter = itk.TubeTK.SegmentTubes[type(image)].New()
            self.segmenter.SetInputImage(image)

    @rpc('segment')
    def segment(self, position, scale):
        if self.segmenter is None:
            raise Exception('segment image is not set')

        # New Stuff
        LowerThreshold = 10
        UpperThreshold = 300
        PixelType = itk.F
        ImageType = itk.Image[PixelType,3]
        ImageType2 = itk.Image[PixelType,2]

        OldImageType = type(self.input_image)
        ImageType = itk.Image[itk.F, 3]
        img = itk.CastImageFilter[OldImageType, ImageType].New()(self.input_image)
        imgRegion = img.GetLargestPossibleRegion()
        indx = imgRegion.GetIndex()
        indx[2] = position[2]
        size = imgRegion.GetSize()
        size[2] = 0
        imgRegionCut = imgRegion
        imgRegionCut.SetIndex(indx)
        imgRegionCut.SetSize(size)
        extractFilter = itk.ExtractImageFilter[ImageType, ImageType2].New()
        extractFilter.SetInput(img)
        extractFilter.SetDirectionCollapseToSubmatrix()
        extractFilter.SetExtractionRegion(imgRegionCut)
        extractFilter.Update()
        img2 = extractFilter.GetOutput()
        connected = itk.ConnectedThresholdImageFilter.New(img2)
        connected.SetLower(LowerThreshold)
        connected.SetUpper(UpperThreshold)
        connected.SetReplaceValue(4096)

        coord2 = itk.Index[2]()
        coord2[0] = position[0]
        coord2[1] = position[1]
        connected.AddSeed(coord2)
        connected.Update()
        mask = connected.GetOutput()

        invert = itk.InvertIntensityImageFilter.New(mask)
        invert.SetMaximum(4096)
        invert.Update()
        maskI = invert.GetOutput()

        distance = itk.DanielssonDistanceMapImageFilter.New(maskI)
        distance.InputIsBinaryOn()
        distance.Update()
        dist = distance.GetOutput()

        minmax = itk.MinimumMaximumImageCalculator.New(dist)
        minmax.Compute()
        radius = minmax.GetMaximum()
        print('Maximally inscribed circle radius in index = ' + str(radius))
        radius = radius * img.GetSpacing()[0]
        print('Maximally inscribed circle radius in point = ' + str(radius))
        radiusIndex = minmax.GetIndexOfMaximum()
        radiusPoint = itk.Point[itk.D, 3]()
        radiusPoint[0] = radiusIndex[0] * img.GetSpacing()[0]
        radiusPoint[1] = radiusIndex[1] * img.GetSpacing()[1]
        radiusPoint[2] = position[2] * img.GetSpacing()[2]
        print('Maximally inscribed circle index = ' + str(radiusIndex))
        print('Maximally inscribed circle point = ' + str(radiusPoint))
        tube = itk.TubeSpatialObject[3].New()
        tubePoint = itk.TubeSpatialObject[3].New()
        tubePoint.SetRadiusInObjectSpace(radius)
        tubePoint.SetPositionInObjectSpace(radiusPoint)
        radiusPoint[0] = radiusPoint[0]+3
        tube.AddPoint(tubePoint)
        radiusPoint[0] = radiusPoint[0]-1
        tube.AddPoint(tubePoint)
        radiusPoint[0] = radiusPoint[0]-1
        tube.AddPoint(tubePoint)
        radiusPoint[0] = radiusPoint[0]-1
        tube.AddPoint(tubePoint)
        radiusPoint[0] = radiusPoint[0]-1
        tube.AddPoint(tubePoint)
        radiusPoint[0] = radiusPoint[0]-1
        tube.AddPoint(tubePoint)
        radiusPoint[0] = radiusPoint[0]-1
        tube.AddPoint(tubePoint)
        print(tube.GetNumberOfPoints())

        # Old Stuff
        #tube = self.segmenter.ExtractTube(position, self.next_tube_id, True)
        if tube is not None:
            self.segmenter.AddTube(tube)
            self.tube_id_mapping[tube.GetId()] = tube
            tube.SetDefaultInsideValue(self.next_tube_id)
            tube.SetDefaultOutsideValue(0)
            # required to update inside/outside value
            tube.Update()
            self.next_tube_id += 1

            rle_mask = self.get_labelmap(tube)

            return {
                'tube': tube,
                'rle_mask': rle_mask,
            }

    @rpc('get_tube_image')
    def get_tube_image(self):
        if self.segmenter is None:
            raise Exception('segment image is not set')

        tube_group = self.segmenter.GetTubeGroup()

        f = itk.SpatialObjectToImageFilter[itk.SpatialObject[3], itk.Image[itk.SS, 3]].New()

        # same origin and spacing and dir as input_image
        f.SetOrigin(self.input_image.GetOrigin())
        f.SetSpacing(self.input_image.GetSpacing())
        f.SetDirection(self.input_image.GetDirection())
        f.SetSize(self.input_image.GetLargestPossibleRegion().GetSize())

        f.SetUseObjectValue(True)
        f.SetOutsideValue(0)

        f.SetInput(tube_group)
        f.Update()

        self.tube_image = f.GetOutput()

        return {
            'vtkClass': 'vtkLabelMap',
            'imageRepresentation': self.tube_image,
            'colorMap': generate_tube_colormap(tube_group),
        }

    @rpc('delete_tubes')
    def delete_tubes(self, tube_ids):
        if self.segmenter is None:
            raise Exception('segment image is not set')

        for id_ in tube_ids:
            tube = self.tube_id_mapping[id_]
            self.segmenter.DeleteTube(tube)
            del self.tube_id_mapping[id_]

    @rpc('root_tubes')
    def tubetree(self, roots):
        tubeGroup = self.segmenter.GetTubeGroup()

        conv = itk.ConvertTubesToTubeTree[3].New()
        conv.SetInput(tubeGroup)
        # TODO add roots, if len(roots) > 0
        conv.SetMaxTubeDistanceToRadiusRatio(2)
        conv.SetMaxContinuityAngleError(180)
        conv.Update()

        children = conv.GetOutput().GetChildren(1) # recursive
        new_parent_ids = []
        for idx in range(len(children)):
            child = itk.down_cast(children[idx])
            new_parent_ids.append((child.GetId(), child.GetParentId()))

        return new_parent_ids
