import numpy as np
import logging
logger = logging.getLogger(__name__)
try:
    from scipy.spatial import Voronoi as qvoronoi
except ImportError:
    qvoronoi = None
    msg = 'scipy.spatial.Voronoi is not available (requires scipy 0.12+), so freud.voronoi is not available.'
    logger.warning(msg)
    #raise ImportWarning(msg)
import _freud
print(dir(_freud))
from _freud import VoronoiBuffer

## Compute the Voronoi tesselation of a 2D or 3D system using qhull
# This essentially just wraps scipy.spatial.Voronoi, but accounts for
# periodic boundary conditions
class Voronoi:
  ##Initialize Voronoi
  # \param box The simulation box
  def __init__(self,box,buff=0.1):
    self.box=box
    self.buff=buff

  ##Set the simulation box
  def setBox(self,box):
    self.box=box
  ##Set the box buffer width
  def setBufferWidth(self,buff):
    self.buff=buff

  ##Compute Voronoi tesselation
  # \param box The simulation box
  # \param buff The buffer of particles to be duplicated to simulated PBC, default=0.1
  def compute(self,positions,box=None,buff=None):
    #if box or buff is not specified, revert to object quantities
    if box is None:
      box=self.box
    if buff is None:
      buff=self.buff

    #Compute the buffer particles in c++
    vbuff = VoronoiBuffer(box)
    vbuff.compute(positions,buff)
    buffer_parts = vbuff.getBufferParticles()
    all_points = np.concatenate((positions,buffer_parts))
    #use qhull to get the points
    vv = qvoronoi(all_points)
    vertices = vv.vertices 
    regions = vv.regions
    points = vv.point_region
    
    #construct a list of polygon/hedra vertices
    self.poly_verts=list()

    #subtract off the particle coordinates
    #from the voronoi polytope

    for p,r in zip(points,positions):
        reg = regions[p]
        pverts = vertices[reg]-r
        self.poly_verts.append(pverts)
  
  #return the list of voronoi polytope vertices
  def getVoronoiPolytopes(self):
    return self.poly_verts
