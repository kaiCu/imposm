# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import division, with_statement

import codecs
from functools import partial

import logging
log = logging.getLogger(__name__)

try:
    import shapely.wkt
    import shapely.geometry
    import shapely.ops
    import shapely.prepared
    geom_support = True
except ImportError:
    geom_support = False

def require_geom_support():
    if not geom_support:
        raise ImportError('Shapely required for geometry support')


def load_datasource(datasource, where=None):
    """
    Loads polygons from any OGR datasource.
    
    Returns the bbox and a Shapely MultiPolygon with
    the loaded geometries.
    """
    from imposm.util.ogr import OGRShapeReader
    
    polygons = []
    for wkt in OGRShapeReader(datasource).wkts(where):
        geom = shapely.wkt.loads(wkt)
        if geom.type == 'Polygon':
            polygons.append(geom)
        elif geom.type == 'MultiPolygon':
            for p in geom:
                polygons.append(p)
        else:
            log.info('skipping %s geometry from %s: not a Polygon/MultiPolygon',
                geom.type, datasource)
    return polygons

def load_polygons(geom_files):
    """
    Loads WKT polygons from one or more text files.
    
    Returns the bbox and a Shapely MultiPolygon with
    the loaded geometries.
    """
    polygons = []
    if isinstance(geom_files, basestring):
        geom_files = [geom_files]
    
    for geom_file in geom_files:
        # open with utf-8-sig encoding to get rid of UTF8 BOM from MS Notepad
        with codecs.open(geom_file, encoding='utf-8-sig') as f:
            polygons.extend(load_polygon_lines(f, source=geom_files))
    
    return polygons

def load_polygon_lines(line_iter, source='<string>'):
    polygons = []
    for line in line_iter:
        if not line.strip():
            continue
        geom = shapely.wkt.loads(line)
        if geom.type == 'Polygon':
            polygons.append(geom)
        elif geom.type == 'MultiPolygon':
            for p in geom:
                polygons.append(p)
        else:
            log.info('ignoring non-polygon geometry (%s) from %s',
                geom.type, source)

    return polygons
    
def build_multipolygon(polygons, simplify=False):
    if polygons:
        mp = shapely.geometry.MultiPolygon(polygons)
        if simplify:
            mp = simplify_geom(mp)
    else:
        mp = shapely.geometry.Polygon()
    return mp.bounds, mp

def simplify_geom(geom):
    bounds = geom.bounds
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    tolerance = min((w/1e6, h/1e6))
    return geom.simplify(tolerance, preserve_topology=True)

def bbox_polygon(bbox):
    """
    Create Polygon that covers the given bbox.
    """
    return shapely.geometry.Polygon((
        (bbox[0], bbox[1]),
        (bbox[2], bbox[1]),
        (bbox[2], bbox[3]),
        (bbox[0], bbox[3]),
        ))

def transform_geometry(from_srs, to_srs, geometry):
    transf = partial(transform_xy, from_srs, to_srs)
    
    if geometry.type == 'Polygon':
        return transform_polygon(transf, geometry)
    
    if geometry.type == 'MultiPolygon':
        return transform_multipolygon(transf, geometry)
    
    raise ValueError('cannot transform %s' % geometry.type)

def transform_polygon(transf, polygon):
    ext = transf(polygon.exterior.xy)
    ints = [transf(ring.xy) for ring in polygon.interiors]
    return shapely.geometry.Polygon(ext, ints)

def transform_multipolygon(transf, multipolygon):
    transformed_polygons = []
    for polygon in multipolygon:
        transformed_polygons.append(transform_polygon(transf, polygon))
    return shapely.geometry.MultiPolygon(transformed_polygons)

def transform_xy(from_srs, to_srs, xy):
    return list(from_srs.transform_to(to_srs, zip(*xy)))
