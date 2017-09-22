import os
import ConfigParser
import geojson
import shapely
from shapely.geometry import Polygon
from shapely.prepared import create_prepared_geometry_object
from math import floor, ceil


# Maximum resolution
MAXRESOLUTION = 156543.0339

# X/Y axis limit
max = MAXRESOLUTION * 256 / 2


class ZoomStepCalculator:

    def __init__(self, shape, zoom_level):
        self.step = _get_tile_size_in_meters_at_required(zoom_level)
        self.shape = shape

        self.minimum_x = int(floor((self._get_minimum_x() + max) / self.step))
        self.maximum_x = int(ceil((self._get_maximum_x() + max) / self.step))
        self.minimum_y = int(floor((self._get_minimum_y() + max) / self.step))
        self.maximum_y = int(ceil((self._get_maximum_y() + max) / self.step))

    def _get_maximum_y(self):
        return self.shape.bounds[3]

    def _get_maximum_x(self):
        return self.shape.bounds[2]

    def _get_minimum_y(self):
        return self.shape.bounds[1]

    def _get_minimum_x(self):
        return self.shape.bounds[0]


class TileBuilder(object):

    def __init__(self, parameter):
        self.a = parameter

    def create_square(self, i, j):
        xmin = i * self.a - max
        ymin = j * self.a - max
        xmax = (i + 1) * self.a - max
        ymax = (j + 1) * self.a - max
        return Polygon([(xmin, ymin), (xmax, ymin),
                        (xmax, ymax), (xmin, ymax)])


# This method finds the tiles that intersect the given geometry for the given
# zoom
def get_tiles_in_geometry(shape, zoom_level):
    step_coordinates = ZoomStepCalculator(shape, zoom_level)
    tb = TileBuilder(step_coordinates.step)
    return _calculate_tiles(shape, step_coordinates, tb)


def _calculate_tiles(shape, step_coordinates, tb):
    tiles = []
    prepared_geometry = create_prepared_geometry_object(shape)
    for i in range(step_coordinates.minimum_x, step_coordinates.maximum_x + 1):
        for j in range(step_coordinates.minimum_y, step_coordinates.maximum_y + 1):
            tile = tb.create_square(i, j)
            if prepared_geometry.intersects(tile):
                tiles.append((i, j, tile))
    return tiles


def _get_tile_size_in_meters_at_required(zoom_level):
    return max / (2 ** (zoom_level - 1))


def load_local_settings(settings):
    local_settings_path = os.environ.get('LOCAL_SETTINGS_PATH',
                                         settings['local_settings_path'])
    if os.path.exists(local_settings_path):
        config = ConfigParser.ConfigParser()
        config.read(local_settings_path)
        settings.update(config.items('app:main'))


def parse_feature(feature):
    if isinstance(feature.geometry, (geojson.geometry.Polygon,
                                     geojson.geometry.MultiPolygon)):
        feature.geometry = shapely.geometry.asShape(feature.geometry)
        return feature
    else:
        return None


def parse_geojson(input):
    collection = geojson.loads(input,
                               object_hook=geojson.GeoJSON.to_instance)

    if not hasattr(collection, "features") or \
            len(collection.features) < 1:
        raise ValueError("GeoJSON file doesn't contain any feature.")
# need translation

    shapely_features = filter(lambda x: x is not None,
                              map(parse_feature, collection.features))

    if len(shapely_features) == 0:
        raise ValueError("GeoJSON file doesn't contain any polygon nor " +
                         "multipolygon.")
# need translation

    return shapely_features


# converts a list of (multi)polygon geometries to one single multipolygon
def convert_to_multipolygon(features):
    from shapely.geometry import MultiPolygon

    rings = []
    for feature in features:
        if isinstance(feature.geometry, MultiPolygon):
            rings = rings + [geom for geom in feature.geometry.geoms]
        else:
            rings = rings + [feature.geometry]

    geometry = MultiPolygon(rings)

    # Downsample 3D -> 2D
    wkt2d = geometry.to_wkt()
    geom2d = shapely.wkt.loads(wkt2d)

    return geom2d
