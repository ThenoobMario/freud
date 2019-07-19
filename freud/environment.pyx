# Copyright (c) 2010-2019 The Regents of the University of Michigan
# This file is from the freud project, released under the BSD 3-Clause License.

R"""
The :class:`freud.environment` module contains functions which characterize the
local environments of particles in the system. These methods use the positions
and orientations of particles in the local neighborhood of a given particle to
characterize the particle environment.
"""

import freud.common
import numpy as np
import warnings
import freud.locality

from freud.common cimport Compute
from freud.util cimport vec3, quat
from libcpp.vector cimport vector
from libcpp.map cimport map
from cython.operator cimport dereference
cimport freud.box
cimport freud._environment
cimport freud.locality

cimport numpy as np

# numpy must be initialized. When using numpy from C or Cython you must
# _always_ do that, or you will have segfaults
np.import_array()


cdef class BondOrder(Compute):
    R"""Compute the bond orientational order diagram for the system of
    particles.

    The bond orientational order diagram (BOOD) is a way of studying the
    average local environments experienced by particles. In a BOOD, a particle
    and its nearest neighbors (determined by either a prespecified number of
    neighbors or simply a cutoff distance) are treated as connected by a bond
    joining their centers. All of the bonds in the system are then binned by
    their azimuthal (:math:`\theta`) and polar (:math:`\phi`) angles to
    indicate the location of a particle's neighbors relative to itself. The
    distance between the particle and its neighbor is only important when
    determining whether it is counted as a neighbor, but is not part of the
    BOOD; as such, the BOOD can be viewed as a projection of all bonds onto the
    unit sphere. The resulting 2D histogram provides insight into how particles
    are situated relative to one-another in a system.

    This class provides access to the classical BOOD as well as a few useful
    variants. These variants can be accessed *via* the :code:`mode` arguments
    to the :meth:`~BondOrder.compute` or :meth:`~BondOrder.accumulate`
    methods. Available modes of calculation are:

    * :code:`'bod'` (Bond Order Diagram, *default*):
      This mode constructs the default BOOD, which is the 2D histogram
      containing the number of bonds formed through each azimuthal
      :math:`\left( \theta \right)` and polar :math:`\left( \phi \right)`
      angle.

    * :code:`'lbod'` (Local Bond Order Diagram):
      In this mode, a particle's neighbors are rotated into the local frame of
      the particle before the BOOD is calculated, *i.e.* the directions of
      bonds are determined relative to the orientation of the particle rather
      than relative to the global reference frame. An example of when this mode
      would be useful is when a system is composed of multiple grains of the
      same crystal; the normal BOOD would show twice as many peaks as expected,
      but using this mode, the bonds would be superimposed.

    * :code:`'obcd'` (Orientation Bond Correlation Diagram):
      This mode aims to quantify the degree of orientational as well as
      translational ordering. As a first step, the rotation that would align a
      particle's neighbor with the particle is calculated. Then, the neighbor
      is rotated **around the central particle** by that amount, which actually
      changes the direction of the bond. One example of how this mode could be
      useful is in identifying plastic crystals, which exhibit translational
      but not orientational ordering. Normally, the BOOD for a plastic crystal
      would exhibit clear structure since there is translational order, but
      with this mode, the neighbor positions would actually be modified,
      resulting in an isotropic (disordered) BOOD.

    * :code:`'oocd'` (Orientation Orientation Correlation Diagram):
      This mode is substantially different from the other modes. Rather than
      compute the histogram of neighbor bonds, this mode instead computes a
      histogram of the directors of neighboring particles, where the director
      is defined as the basis vector :math:`\hat{z}` rotated by the neighbor's
      quaternion. The directors are then rotated into the central particle's
      reference frame. This mode provides insight into the local orientational
      environment of particles, indicating, on average, how a particle's
      neighbors are oriented.

    .. moduleauthor:: Erin Teich <erteich@umich.edu>

    Args:
        r_max (float):
            Distance over which to calculate.
        num_neighbors (unsigned int):
            Number of neighbors to find.
        n_bins_t (unsigned int):
            Number of :math:`\theta` bins.
        n_bins_p (unsigned int):
            Number of :math:`\phi` bins.

    Attributes:
        bond_order (:math:`\left(N_{\phi}, N_{\theta} \right)` :class:`numpy.ndarray`):
            Bond order.
        box (:class:`freud.box.Box`):
            Box used in the calculation.
        theta (:math:`\left(N_{\theta} \right)` :class:`numpy.ndarray`):
            The values of bin centers for :math:`\theta`.
        phi (:math:`\left(N_{\phi} \right)` :class:`numpy.ndarray`):
            The values of bin centers for :math:`\phi`.
        n_bins_theta (unsigned int):
            The number of bins in the :math:`\theta` dimension.
        n_bins_phi (unsigned int):
            The number of bins in the :math:`\phi` dimension.

    """  # noqa: E501
    cdef freud._environment.BondOrder * thisptr
    cdef num_neigh
    cdef r_max
    cdef n_bins_t
    cdef n_bins_p

    def __cinit__(self, float r_max, unsigned int num_neighbors,
                  unsigned int n_bins_t, unsigned int n_bins_p):
        if n_bins_t < 2:
            raise ValueError("Must have at least 2 bins in theta.")
        if n_bins_p < 2:
            raise ValueError("Must have at least 2 bins in phi.")
        self.thisptr = new freud._environment.BondOrder(
            r_max, num_neighbors, n_bins_t, n_bins_p)
        self.r_max = r_max
        self.num_neigh = num_neighbors
        self.n_bins_t = n_bins_t
        self.n_bins_p = n_bins_p

    def __dealloc__(self):
        del self.thisptr

    @Compute._compute()
    def accumulate(self, box, ref_points, ref_orientations, points=None,
                   orientations=None, str mode="bod", nlist=None):
        R"""Calculates the correlation function and adds to the current
        histogram.

        Args:
            box (:class:`freud.box.Box`):
                Simulation box.
            ref_points ((:math:`N_{ref\_points}`, 3) :class:`numpy.ndarray`):
                Reference points used to calculate bonds.
            ref_orientations ((:math:`N_{ref\_points}`, 4) :class:`numpy.ndarray`):
                Reference orientations used to calculate bonds.
            points ((:math:`N_{points}`, 3) :class:`numpy.ndarray`, optional):
                Points used to calculate bonds. Uses :code:`ref_points` if not
                provided or :code:`None`.
                (Default value = :code:`None`).
            orientations ((:math:`N_{points}`, 4) :class:`numpy.ndarray`, optional):
                Orientations used to calculate bonds. Uses
                :code:`ref_orientations` if not provided or :code:`None`.
                (Default value = :code:`None`).
            mode (str, optional):
                Mode to calculate bond order. Options are :code:`'bod'`,
                :code:`'lbod'`, :code:`'obcd'`, or :code:`'oocd'`
                (Default value = :code:`'bod'`).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value =
                :code:`None`).
        """  # noqa: E501
        cdef freud.box.Box b = freud.common.convert_box(box)

        exclude_ii = points is None

        nq_nlist = freud.locality.make_nq_nlist(b, ref_points, nlist)
        cdef freud.locality.NeighborQuery nq = nq_nlist[0]
        cdef freud.locality.NlistptrWrapper nlistptr = nq_nlist[1]

        cdef freud.locality._QueryArgs qargs = freud.locality._QueryArgs(
            mode="nearest", nn=self.num_neigh,
            r_max=self.r_max, exclude_ii=exclude_ii)
        ref_points = nq.points

        if points is None:
            points = ref_points
        if orientations is None:
            orientations = ref_orientations

        points = freud.common.convert_array(points, shape=(None, 3))
        ref_orientations = freud.common.convert_array(
            ref_orientations, shape=(ref_points.shape[0], 4))
        orientations = freud.common.convert_array(
            orientations, shape=(points.shape[0], 4))

        cdef unsigned int index = 0
        if mode == "bod":
            index = 0
        elif mode == "lbod":
            index = 1
        elif mode == "obcd":
            index = 2
        elif mode == "oocd":
            index = 3
        else:
            raise RuntimeError(
                ('Unknown BOD mode: {}. Options are:'
                    'bod, lbod, obcd, oocd.').format(mode))

        cdef const float[:, ::1] l_points = points
        cdef const float[:, ::1] l_ref_orientations = ref_orientations
        cdef const float[:, ::1] l_orientations = orientations
        cdef unsigned int n_p = l_points.shape[0]

        with nogil:
            self.thisptr.accumulate(
                nlistptr.get_ptr(),
                nq.get_ptr(),
                <quat[float]*> &l_ref_orientations[0, 0],
                <vec3[float]*> &l_points[0, 0],
                <quat[float]*> &l_orientations[0, 0],
                n_p,
                index, dereference(qargs.thisptr))
        return self

    @Compute._computed_property()
    def bond_order(self):
        cdef unsigned int n_bins_phi = self.thisptr.getNBinsPhi()
        cdef unsigned int n_bins_theta = self.thisptr.getNBinsTheta()
        cdef float[:, ::1] bod = <float[:n_bins_phi, :n_bins_theta]> \
            self.thisptr.getBondOrder().get()
        result = np.asarray(bod)
        return result

    @Compute._computed_property()
    def box(self):
        return freud.box.BoxFromCPP(self.thisptr.getBox())

    @Compute._reset
    def reset(self):
        R"""Resets the values of the bond order in memory."""
        self.thisptr.reset()

    @Compute._compute()
    def compute(self, box, ref_points, ref_orientations, points=None,
                orientations=None, mode="bod", nlist=None):
        R"""Calculates the bond order histogram. Will overwrite the current
        histogram.

        Args:
            box (:class:`freud.box.Box`):
                Simulation box.
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Reference points used to calculate bonds.
            ref_orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                Reference orientations used to calculate bonds.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`, optional):
                Points used to calculate bonds. Uses :code:`ref_points` if not
                provided or :code:`None`.
                (Default value = :code:`None`).
            orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`, optional):
                Orientations used to calculate bonds. Uses
                :code:`ref_orientations` if not provided or :code:`None`.
                (Default value = :code:`None`).
            mode (str, optional):
                Mode to calculate bond order. Options are :code:`'bod'`,
                :code:`'lbod'`, :code:`'obcd'`, or :code:`'oocd'`
                (Default value = :code:`'bod'`).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value =
                :code:`None`).
        """  # noqa: E501
        self.reset()
        self.accumulate(box, ref_points, ref_orientations,
                        points, orientations, mode, nlist)
        return self

    @property
    def theta(self):
        cdef unsigned int n_bins_theta = self.thisptr.getNBinsTheta()
        if not n_bins_theta:
            return np.asarray([], dtype=np.float32)
        cdef const float[::1] theta = \
            <float[:n_bins_theta]> self.thisptr.getTheta().get()
        return np.asarray(theta)

    @property
    def phi(self):
        cdef unsigned int n_bins_phi = self.thisptr.getNBinsPhi()
        if not n_bins_phi:
            return np.asarray([], dtype=np.float32)
        cdef const float[::1] phi = \
            <float[:n_bins_phi]> self.thisptr.getPhi().get()
        return np.asarray(phi)

    @property
    def n_bins_theta(self):
        return self.thisptr.getNBinsTheta()

    @property
    def n_bins_phi(self):
        return self.thisptr.getNBinsPhi()

    def __repr__(self):
        return ("freud.environment.{cls}(r_max={r_max}, "
                "num_neighbors={num_neigh}, n_bins_t={n_bins_t}, "
                "n_bins_p={n_bins_p})").format(cls=type(self).__name__,
                                               r_max=self.r_max,
                                               num_neigh=self.num_neigh,
                                               n_bins_t=self.n_bins_t,
                                               n_bins_p=self.n_bins_p)

    def __str__(self):
        return repr(self)


cdef class LocalDescriptors(Compute):
    R"""Compute a set of descriptors (a numerical "fingerprint") of a particle's
    local environment.

    The resulting spherical harmonic array will be a complex-valued
    array of shape `(num_bonds, num_sphs)`. Spherical harmonic
    calculation can be restricted to some number of nearest neighbors
    through the `num_neighbors` argument; if a particle has more bonds
    than this number, the last one or more rows of bond spherical
    harmonics for each particle will not be set.

    .. moduleauthor:: Matthew Spellings <mspells@umich.edu>

    Args:
        num_neighbors (unsigned int):
            Maximum number of neighbors to compute descriptors for.
        lmax (unsigned int):
            Maximum spherical harmonic :math:`l` to consider.
        r_max (float):
            Initial guess of the maximum radius to looks for neighbors.
        negative_m (bool, optional):
            True if we should also calculate :math:`Y_{lm}` for negative
            :math:`m`. (Default value = :code:`True`)

    Attributes:
        sph (:math:`\left(N_{bonds}, \text{SphWidth} \right)` :class:`numpy.ndarray`):
            A reference to the last computed spherical harmonic array.
        num_particles (unsigned int):
            The number of points passed to the last call to :meth:`~.compute`.
        num_neighbors (unsigned int):
            The number of neighbors used by the last call to compute. Bounded
            from above by the number of reference points multiplied by the
            lower of the num_neighbors arguments passed to the last compute
            call or the constructor.
        l_max (unsigned int):
            The maximum spherical harmonic :math:`l` to calculate for.
        r_max (float):
            The cutoff radius.
    """  # noqa: E501
    cdef freud._environment.LocalDescriptors * thisptr
    cdef num_neigh
    cdef r_max
    cdef lmax
    cdef negative_m

    known_modes = {'neighborhood': freud._environment.LocalNeighborhood,
                   'global': freud._environment.Global,
                   'particle_local': freud._environment.ParticleLocal}

    def __cinit__(self, num_neighbors, lmax, r_max, negative_m=True):
        self.thisptr = new freud._environment.LocalDescriptors(
            lmax, negative_m)
        self.num_neigh = num_neighbors
        self.r_max = r_max
        self.lmax = lmax
        self.negative_m = negative_m

    def __dealloc__(self):
        del self.thisptr

    @Compute._compute()
    def compute(self, box, unsigned int num_neighbors, ref_points, points=None,
                orientations=None, mode='neighborhood', nlist=None):
        R"""Calculates the local descriptors of bonds from a set of source
        points to a set of destination points.

        Args:
            box (:class:`freud.box.Box`):
                Simulation box.
            num_neighbors (unsigned int):
                Number of nearest neighbors to compute with or to limit to, if the
                neighbor list is precomputed.
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Source points to calculate the order parameter.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`, optional):
                Destination points to calculate the order parameter
                (Default value = :code:`None`).
            orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`, optional):
                Orientation of each reference point (Default value =
                :code:`None`).
            mode (str, optional):
                Orientation mode to use for environments, either
                :code:`'neighborhood'` to use the orientation of the local
                neighborhood, :code:`'particle_local'` to use the given
                particle orientations, or :code:`'global'` to not rotate
                environments (Default value = :code:`'neighborhood'`).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value = :code:`None`).
        """  # noqa: E501
        cdef freud.box.Box b = freud.common.convert_box(box)

        if mode not in self.known_modes:
            raise RuntimeError(
                'Unknown LocalDescriptors orientation mode: {}'.format(mode))

        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))

        exclude_ii = points is None
        if points is None:
            points = ref_points

        points = freud.common.convert_array(points, shape=(None, 3))

        # The l_orientations_ptr is only used for 'particle_local' mode.
        cdef const float[:, ::1] l_orientations
        cdef quat[float]* l_orientations_ptr = NULL
        if mode == 'particle_local':
            if orientations is None:
                raise RuntimeError(
                    ('Orientations must be given to orient LocalDescriptors '
                        'with particles\' orientations'))

            orientations = freud.common.convert_array(
                orientations, shape=(ref_points.shape[0], 4))

            l_orientations = orientations
            l_orientations_ptr = <quat[float]*> &l_orientations[0, 0]

        cdef const float[:, ::1] l_ref_points = ref_points
        cdef unsigned int nRef = l_ref_points.shape[0]
        cdef const float[:, ::1] l_points = points
        cdef unsigned int nP = l_points.shape[0]
        cdef freud._environment.LocalDescriptorOrientation l_mode

        l_mode = self.known_modes[mode]

        self.num_neigh = num_neighbors

        defaulted_nlist = freud.locality.make_default_nlist_nn(
            b, ref_points, points, self.num_neigh, nlist,
            exclude_ii, self.r_max)
        cdef freud.locality.NeighborList nlist_ = defaulted_nlist[0]

        with nogil:
            self.thisptr.compute(
                dereference(b.thisptr),
                nlist_.get_ptr(),
                num_neighbors,
                <vec3[float]*> &l_ref_points[0, 0],
                nRef, <vec3[float]*> &l_points[0, 0], nP,
                l_orientations_ptr, l_mode)
        return self

    @Compute._computed_property()
    def sph(self):
        cdef unsigned int n_sphs = self.thisptr.getNSphs()
        cdef unsigned int sph_width = self.thisptr.getSphWidth()
        if not n_sphs or not sph_width:
            return np.asarray([[]], dtype=np.complex64)
        cdef np.complex64_t[:, ::1] sph = \
            <np.complex64_t[:n_sphs, :sph_width]> \
            self.thisptr.getSph().get()
        return np.asarray(sph, dtype=np.complex64)

    @Compute._computed_property()
    def num_particles(self):
        return self.thisptr.getNP()

    @Compute._computed_property()
    def num_neighbors(self):
        return self.thisptr.getNSphs()

    @property
    def l_max(self):
        return self.thisptr.getLMax()

    def __repr__(self):
        return ("freud.environment.{cls}(num_neighbors={num_neigh}, "
                "lmax={lmax}, r_max={r_max}, "
                "negative_m={negative_m})").format(cls=type(self).__name__,
                                                   num_neigh=self.num_neigh,
                                                   lmax=self.lmax,
                                                   r_max=self.r_max,
                                                   negative_m=self.negative_m)

    def __str__(self):
        return repr(self)


cdef class MatchEnv(Compute):
    R"""Clusters particles according to whether their local environments match
    or not, according to various shape matching metrics.

    .. moduleauthor:: Erin Teich <erteich@umich.edu>

    Args:
        box (:class:`freud.box.Box`):
            Simulation box.
        r_max (float):
            Cutoff radius for cell list and clustering algorithm. Values near
            the first minimum of the RDF are recommended.
        num_neighbors (unsigned int):
            Number of nearest neighbors taken to define the local environment
            of any given particle.

    Attributes:
        tot_environment (:math:`\left(N_{particles}, N_{neighbors}, 3\right)` :class:`numpy.ndarray`):
            All environments for all particles.
        num_particles (unsigned int):
            The number of particles.
        num_clusters (unsigned int):
            The number of clusters.
        clusters (:math:`\left(N_{particles}\right)` :class:`numpy.ndarray`):
            The per-particle index indicating cluster membership.
    """  # noqa: E501
    cdef freud._environment.MatchEnv * thisptr
    cdef r_max
    cdef num_neigh
    cdef m_box

    def __cinit__(self, box, r_max, num_neighbors):
        cdef freud.box.Box b = freud.common.convert_box(box)

        self.thisptr = new freud._environment.MatchEnv(
            dereference(b.thisptr), r_max, num_neighbors)

        self.r_max = r_max
        self.num_neigh = num_neighbors
        self.m_box = box

    def __dealloc__(self):
        del self.thisptr

    def setBox(self, box):
        R"""Reset the simulation box.

        Args:
            box (:class:`freud.box.Box`): Simulation box.
        """
        cdef freud.box.Box b = freud.common.convert_box(box)
        self.thisptr.setBox(dereference(b.thisptr))
        self.m_box = box

    @Compute._compute()
    def cluster(self, points, threshold, hard_r=False, registration=False,
                global_search=False, env_nlist=None, nlist=None):
        R"""Determine clusters of particles with matching environments.

        Args:
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Destination points to calculate the order parameter.
            threshold (float):
                Maximum magnitude of the vector difference between two vectors,
                below which they are "matching."
            hard_r (bool):
                If True, add all particles that fall within the threshold of
                m_r_maxsq to the environment.
            registration (bool, optional):
                If True, first use brute force registration to orient one set
                of environment vectors with respect to the other set such that
                it minimizes the RMSD between the two sets.
                (Default value = :code:`False`)
            global_search (bool, optional):
                If True, do an exhaustive search wherein the environments of
                every single pair of particles in the simulation are compared.
                If False, only compare the environments of neighboring
                particles. (Default value = :code:`False`)
            env_nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find the environment of every particle
                (Default value = :code:`None`).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find neighbors of every particle, to
                compare environments (Default value = :code:`None`).
        """
        points = freud.common.convert_array(points, shape=(None, 3))

        cdef const float[:, ::1] l_points = points
        cdef unsigned int nP = l_points.shape[0]

        cdef freud.locality.NeighborList nlist_
        cdef freud.locality.NeighborList env_nlist_
        if hard_r:
            defaulted_nlist = freud.locality.make_default_nlist(
                self.m_box, points, points, self.r_max, nlist, True)
            nlist_ = defaulted_nlist[0]

            defaulted_env_nlist = freud.locality.make_default_nlist(
                self.m_box, points, points, self.r_max, env_nlist, True)
            env_nlist_ = defaulted_env_nlist[0]
        else:
            defaulted_nlist = freud.locality.make_default_nlist_nn(
                self.m_box, points, points, self.num_neigh, nlist,
                True, self.r_max)
            nlist_ = defaulted_nlist[0]

            defaulted_env_nlist = freud.locality.make_default_nlist_nn(
                self.m_box, points, points, self.num_neigh, env_nlist,
                True, self.r_max)
            env_nlist_ = defaulted_env_nlist[0]

        self.thisptr.cluster(
            env_nlist_.get_ptr(), nlist_.get_ptr(),
            <vec3[float]*> &l_points[0, 0], nP, threshold, hard_r,
            registration, global_search)
        return self

    @Compute._compute()
    def matchMotif(self, points, ref_points, threshold, registration=False,
                   nlist=None):
        R"""Determine clusters of particles that match the motif provided by
        ref_points.

        Args:
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Vectors that make up the motif against which we are matching.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Particle positions.
            threshold (float):
                Maximum magnitude of the vector difference between two vectors,
                below which they are considered "matching."
            registration (bool, optional):
                If True, first use brute force registration to orient one set
                of environment vectors with respect to the other set such that
                it minimizes the RMSD between the two sets
                (Default value = False).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value =
                :code:`None`).
        """
        points = freud.common.convert_array(points, shape=(None, 3))
        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))

        cdef np.ndarray[float, ndim=1] l_points = np.ascontiguousarray(
            points.flatten())
        cdef np.ndarray[float, ndim=1] l_ref_points = np.ascontiguousarray(
            ref_points.flatten())
        cdef unsigned int nP = l_points.shape[0]
        cdef unsigned int nRef = l_ref_points.shape[0]

        defaulted_nlist = freud.locality.make_default_nlist_nn(
            self.m_box, points, points,
            self.num_neigh, nlist, True, self.r_max)
        cdef freud.locality.NeighborList nlist_ = defaulted_nlist[0]

        self.thisptr.matchMotif(
            nlist_.get_ptr(), <vec3[float]*> &l_points[0], nP,
            <vec3[float]*> &l_ref_points[0], nRef, threshold,
            registration)

    @Compute._compute()
    def minRMSDMotif(self, ref_points, points, registration=False, nlist=None):
        R"""Rotate (if registration=True) and permute the environments of all
        particles to minimize their RMSD with respect to the motif provided by
        ref_points.

        Args:
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Vectors that make up the motif against which we are matching.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Particle positions.
            registration (bool, optional):
                If True, first use brute force registration to orient one set
                of environment vectors with respect to the other set such that
                it minimizes the RMSD between the two sets
                (Default value = :code:`False`).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value =
                :code:`None`).
        Returns:
            :math:`\left(N_{particles}\right)` :class:`numpy.ndarray`:
                Vector of minimal RMSD values, one value per particle.

        """
        points = freud.common.convert_array(points, shape=(None, 3))
        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))

        cdef np.ndarray[float, ndim=1] l_points = np.ascontiguousarray(
            points.flatten())
        cdef np.ndarray[float, ndim=1] l_ref_points = np.ascontiguousarray(
            ref_points.flatten())
        cdef unsigned int nP = l_points.shape[0]
        cdef unsigned int nRef = l_ref_points.shape[0]

        defaulted_nlist = freud.locality.make_default_nlist_nn(
            self.m_box, points, points,
            self.num_neigh, nlist, True, self.r_max)
        cdef freud.locality.NeighborList nlist_ = defaulted_nlist[0]

        cdef vector[float] min_rmsd_vec = self.thisptr.minRMSDMotif(
            nlist_.get_ptr(), <vec3[float]*> &l_points[0], nP,
            <vec3[float]*> &l_ref_points[0], nRef, registration)

        return min_rmsd_vec

    def isSimilar(self, ref_points, points,
                  threshold, registration=False):
        R"""Test if the motif provided by ref_points is similar to the motif
        provided by points.

        Args:
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Vectors that make up motif 1.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Vectors that make up motif 2.
            threshold (float):
                Maximum magnitude of the vector difference between two vectors,
                below which they are considered "matching."
            registration (bool, optional):
                If True, first use brute force registration to orient one set
                of environment vectors with respect to the other set such that
                it minimizes the RMSD between the two sets
                (Default value = :code:`False`).

        Returns:
            tuple ((:math:`\left(N_{particles}, 3\right)` :class:`numpy.ndarray`), map[int, int]):
                A doublet that gives the rotated (or not) set of
                :code:`points`, and the mapping between the vectors of
                :code:`ref_points` and :code:`points` that will make them
                correspond to each other. Empty if they do not correspond to
                each other.
        """  # noqa: E501
        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))
        points = freud.common.convert_array(points, shape=(None, 3))

        cdef const float[:, ::1] l_ref_points = ref_points
        cdef const float[:, ::1] l_points = points
        cdef unsigned int nRef1 = l_ref_points.shape[0]
        cdef unsigned int nRef2 = l_points.shape[0]
        cdef float threshold_sq = threshold*threshold

        if nRef1 != nRef2:
            raise ValueError(
                ("The number of vectors in ref_points must MATCH"
                 "the number of vectors in points"))

        cdef map[unsigned int, unsigned int] vec_map = self.thisptr.isSimilar(
            <vec3[float]*> &l_ref_points[0, 0],
            <vec3[float]*> &l_points[0, 0],
            nRef1, threshold_sq, registration)
        return [np.asarray(l_points), vec_map]

    def minimizeRMSD(self, ref_points, points, registration=False):
        R"""Get the somewhat-optimal RMSD between the set of vectors ref_points
        and the set of vectors points.

        Args:
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Vectors that make up motif 1.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Vectors that make up motif 2.
            registration (bool, optional):
                If true, first use brute force registration to orient one set
                of environment vectors with respect to the other set such that
                it minimizes the RMSD between the two sets
                (Default value = :code:`False`).

        Returns:
            tuple (float, (:math:`\left(N_{particles}, 3\right)` :class:`numpy.ndarray`), map[int, int]):
                A triplet that gives the associated min_rmsd, rotated (or not)
                set of points, and the mapping between the vectors of
                ref_points and points that somewhat minimizes the RMSD.
        """  # noqa: E501
        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))
        points = freud.common.convert_array(points, shape=(None, 3))

        cdef const float[:, ::1] l_ref_points = ref_points
        cdef const float[:, ::1] l_points = points
        cdef unsigned int nRef1 = l_ref_points.shape[0]
        cdef unsigned int nRef2 = l_points.shape[0]

        if nRef1 != nRef2:
            raise ValueError(
                ("The number of vectors in ref_points must MATCH"
                 "the number of vectors in points"))

        cdef float min_rmsd = -1
        cdef map[unsigned int, unsigned int] results_map = \
            self.thisptr.minimizeRMSD(
                <vec3[float]*> &l_ref_points[0, 0],
                <vec3[float]*> &l_points[0, 0],
                nRef1, min_rmsd, registration)
        return [min_rmsd, np.asarray(l_points), results_map]

    @Compute._computed_property()
    def clusters(self):
        cdef unsigned int n_particles = self.thisptr.getNP()
        if not n_particles:
            return np.asarray([], dtype=np.uint32)
        cdef const unsigned int[::1] clusters = \
            <unsigned int[:n_particles]> self.thisptr.getClusters().get()
        return np.asarray(clusters)

    @Compute._computed_method()
    def getEnvironment(self, i):
        R"""Returns the set of vectors defining the environment indexed by i.

        Args:
            i (unsigned int): Environment index.

        Returns:
            :math:`\left(N_{neighbors}, 3\right)` :class:`numpy.ndarray`:
            The array of vectors.
        """
        cdef unsigned int max_neighbors = self.thisptr.getMaxNumNeighbors()
        if not max_neighbors:
            return np.asarray([[]], dtype=np.float32)
        cdef const float[:, ::1] environment = \
            <float[:max_neighbors, :3]> (
                <float*> self.thisptr.getEnvironment(i).get())
        return np.asarray(environment)

    @Compute._computed_property()
    def tot_environment(self):
        cdef unsigned int n_particles = self.thisptr.getNP()
        cdef unsigned int max_neighbors = self.thisptr.getMaxNumNeighbors()
        if not n_particles or not max_neighbors:
            return np.asarray([[[]]], dtype=np.float32)
        cdef const float[:, :, ::1] tot_environment = \
            <float[:n_particles, :max_neighbors, :3]> (
                <float*> self.thisptr.getTotEnvironment().get())
        return np.asarray(tot_environment)

    @Compute._computed_property()
    def num_particles(self):
        return self.thisptr.getNP()

    @Compute._computed_property()
    def num_clusters(self):
        return self.thisptr.getNumClusters()

    def __repr__(self):
        return ("freud.environment.{cls}(box={box}, "
                "r_max={r}, num_neighbors={k})").format(
                    cls=type(self).__name__, box=self.m_box.__repr__(),
                    r=self.r_max, k=self.num_neigh)

    def __str__(self):
        return repr(self)

    @Compute._computed_method()
    def plot(self, ax=None):
        """Plot cluster distribution.

        Args:
            ax (:class:`matplotlib.axes.Axes`, optional): Axis to plot on. If
                :code:`None`, make a new figure and axis.
                (Default value = :code:`None`)

        Returns:
            (:class:`matplotlib.axes.Axes`): Axis with the plot.
        """
        import plot
        try:
            counts = np.unique(self.clusters, return_counts=True)
        except ValueError:
            return None
        return plot.plot_clusters(counts[0], counts[1],
                                  num_cluster_to_plot=10,
                                  ax=ax)

    def _repr_png_(self):
        import plot
        try:
            return plot.ax_to_bytes(self.plot())
        except AttributeError:
            return None


cdef class AngularSeparation(Compute):
    R"""Calculates the minimum angles of separation between particles and
    references.

    .. moduleauthor:: Erin Teich <erteich@umich.edu>
    .. moduleauthor:: Andrew Karas <askaras@umich.edu>

    Args:
        r_max (float):
            Cutoff radius for cell list and clustering algorithm. Values near
            the first minimum of the RDF are recommended.
        num_neighbors (int):
            The number of neighbors.

    Attributes:
        nlist (:class:`freud.locality.NeighborList`):
            The neighbor list.
        n_p (unsigned int):
            The number of particles used in computing the last set.
        n_ref (unsigned int):
            The number of reference particles used in computing the neighbor
            angles.
        n_global (unsigned int):
            The number of global orientations to check against.
        neighbor_angles (:math:`\left(N_{bonds}\right)` :class:`numpy.ndarray`):
            The neighbor angles in radians. **This field is only populated
            after** :meth:`~.computeNeighbor` **is called.** The angles
            are stored in the order of the neighborlist object.
        global_angles (:math:`\left(N_{particles}, N_{global} \right)` :class:`numpy.ndarray`):
            The global angles in radians. **This field is only populated
            after** :meth:`~.computeGlobal` **is called.** The angles
            are stored in the order of the neighborlist object.

    .. todo Need to figure out what happens if you use a neighborlist with
            strict_cut=True
    """  # noqa: E501
    cdef freud._environment.AngularSeparation * thisptr
    cdef unsigned int num_neigh
    cdef float r_max
    cdef freud.locality.NeighborList nlist_

    def __cinit__(self, float r_max, unsigned int num_neighbors):
        self.thisptr = new freud._environment.AngularSeparation()
        self.r_max = r_max
        self.num_neigh = num_neighbors

    def __dealloc__(self):
        del self.thisptr

    @property
    def nlist(self):
        return self.nlist_

    @Compute._compute("computeNeighbor")
    def computeNeighbor(self, box, ref_orientations, orientations,
                        ref_points, points=None,
                        equiv_quats=np.array([[1, 0, 0, 0]]), nlist=None):
        R"""Calculates the minimum angles of separation between ref_orientations and orientations,
        checking for underlying symmetry as encoded in equiv_quats. The result
        is stored in the :code:`neighbor_angles` class attribute.

        Args:
            box (:class:`freud.box.Box`):
                Simulation box.
            ref_orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                Reference orientations used to calculate the order parameter.
            orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                Orientations used to calculate the order parameter.
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Reference points used to calculate the order parameter.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Points used to calculate the order parameter.
            equiv_quats ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`, optional):
                The set of all equivalent quaternions that takes the particle
                as it is defined to some global reference orientation.
                Important: :code:`equiv_quats` must include both :math:`q` and
                :math:`-q`, for all included quaternions.
                (Default value = :code:`[[1, 0, 0, 0]]`)
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value =
                :code:`None`).
        """  # noqa: E501
        cdef freud.box.Box b = freud.common.convert_box(box)
        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))

        exclude_ii = points is None
        if points is None:
            points = ref_points

        points = freud.common.convert_array(points, shape=(None, 3))

        ref_orientations = freud.common.convert_array(
            ref_orientations, shape=(None, 4))
        orientations = freud.common.convert_array(
            orientations, shape=(None, 4))
        equiv_quats = freud.common.convert_array(equiv_quats, shape=(None, 4))

        defaulted_nlist = freud.locality.make_default_nlist_nn(
            b, ref_points, points, self.num_neigh,
            nlist, exclude_ii, self.r_max)
        self.nlist_ = defaulted_nlist[0].copy()

        cdef const float[:, ::1] l_ref_orientations = ref_orientations
        cdef const float[:, ::1] l_orientations = orientations
        cdef const float[:, ::1] l_equiv_quats = equiv_quats

        cdef unsigned int nRef = l_ref_orientations.shape[0]
        cdef unsigned int nP = l_orientations.shape[0]
        cdef unsigned int nEquiv = l_equiv_quats.shape[0]

        with nogil:
            self.thisptr.computeNeighbor(
                self.nlist_.get_ptr(),
                <quat[float]*> &l_ref_orientations[0, 0],
                <quat[float]*> &l_orientations[0, 0],
                <quat[float]*> &l_equiv_quats[0, 0],
                nRef, nP, nEquiv)
        return self

    @Compute._compute("computeGlobal")
    def computeGlobal(self, global_orientations, orientations, equiv_quats):
        R"""Calculates the minimum angles of separation between
        :code:`global_orientations` and :code:`orientations`, checking for underlying symmetry as
        encoded in :code:`equiv_quats`. The result is stored in the
        :code:`global_angles` class attribute.


        Args:
            global_orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                Reference orientations to calculate the order parameter.
            orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                Orientations to calculate the order parameter.
            equiv_quats ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                The set of all equivalent quaternions that takes the particle
                as it is defined to some global reference orientation.
                Important: :code:`equiv_quats` must include both :math:`q` and
                :math:`-q`, for all included quaternions.
        """  # noqa
        global_orientations = freud.common.convert_array(
            global_orientations, shape=(None, 4))
        orientations = freud.common.convert_array(
            orientations, shape=(None, 4))
        equiv_quats = freud.common.convert_array(equiv_quats, shape=(None, 4))

        cdef const float[:, ::1] l_global_orientations = global_orientations
        cdef const float[:, ::1] l_orientations = orientations
        cdef const float[:, ::1] l_equiv_quats = equiv_quats

        cdef unsigned int nGlobal = l_global_orientations.shape[0]
        cdef unsigned int nP = l_orientations.shape[0]
        cdef unsigned int nEquiv = l_equiv_quats.shape[0]

        with nogil:
            self.thisptr.computeGlobal(
                <quat[float]*> &l_global_orientations[0, 0],
                <quat[float]*> &l_orientations[0, 0],
                <quat[float]*> &l_equiv_quats[0, 0],
                nGlobal, nP, nEquiv)
        return self

    @Compute._computed_property("computeNeighbor")
    def neighbor_angles(self):
        cdef unsigned int n_bonds = len(self.nlist)
        if not n_bonds:
            return np.asarray([], dtype=np.float32)
        cdef const float[::1] neighbor_angles = \
            <float[:n_bonds]> self.thisptr.getNeighborAngles().get()
        return np.asarray(neighbor_angles)

    @Compute._computed_property("computeGlobal")
    def global_angles(self):
        cdef unsigned int n_particles = self.thisptr.getNP()
        cdef unsigned int n_global = self.thisptr.getNglobal()
        if not n_particles or not n_global:
            return np.empty((n_particles, n_global), dtype=np.float32)
        cdef const float[:, ::1] global_angles = \
            <float[:n_particles, :n_global]> \
            self.thisptr.getGlobalAngles().get()
        return np.asarray(global_angles)

    @Compute._computed_property(("computeGlobal", "computeNeighbor"))
    def n_p(self):
        return self.thisptr.getNP()

    @Compute._computed_property("computeNeighbor")
    def n_ref(self):
        return self.thisptr.getNref()

    @Compute._computed_property("computeGlobal")
    def n_global(self):
        return self.thisptr.getNglobal()

    def __repr__(self):
        return "freud.environment.{cls}(r_max={r}, num_neighbors={n})".format(
            cls=type(self).__name__, r=self.r_max, n=self.num_neigh)

    def __str__(self):
        return repr(self)

cdef class LocalBondProjection(Compute):
    R"""Calculates the maximal projection of nearest neighbor bonds for each
    particle onto some set of reference vectors, defined in the particles'
    local reference frame.

    .. moduleauthor:: Erin Teich <erteich@umich.edu>

    .. versionadded:: 0.11

    Args:
        r_max (float):
            Cutoff radius.
        num_neighbors (unsigned int):
            The number of neighbors.

    Attributes:
        projections ((:math:`\left(N_{reference}, N_{neighbors}, N_{projection\_vecs} \right)` :class:`numpy.ndarray`):
            The projection of each bond between reference particles and their
            neighbors onto each of the projection vectors.
        normed_projections ((:math:`\left(N_{reference}, N_{neighbors}, N_{projection\_vecs} \right)` :class:`numpy.ndarray`)
            The normalized projection of each bond between reference particles
            and their neighbors onto each of the projection vectors.
        num_reference_particles (int):
            The number of reference points used in the last calculation.
        num_particles (int):
            The number of points used in the last calculation.
        num_proj_vectors (int):
            The number of projection vectors used in the last calculation.
        box (:class:`freud.box.Box`):
            The box used in the last calculation.
        nlist (:class:`freud.locality.NeighborList`):
            The neighbor list generated in the last calculation.
    """  # noqa: E501
    cdef freud._environment.LocalBondProjection * thisptr
    cdef float r_max
    cdef unsigned int num_neigh
    cdef freud.locality.NeighborList nlist_

    def __cinit__(self, r_max, num_neighbors):
        self.thisptr = new freud._environment.LocalBondProjection()
        self.r_max = r_max
        self.num_neigh = int(num_neighbors)

    def __dealloc__(self):
        del self.thisptr

    @Compute._computed_property()
    def nlist(self):
        return self.nlist_

    @Compute._compute()
    def compute(self, box, proj_vecs, ref_points,
                ref_orientations, points=None,
                equiv_quats=np.array([[1, 0, 0, 0]]), nlist=None):
        R"""Calculates the maximal projections of nearest neighbor bonds
        (between :code:`ref_points` and :code:`points`) onto the set of
        reference vectors :code:`proj_vecs`, defined in the local reference
        frames of the :code:`ref_points` as defined by the orientations
        :code:`ref_orientations`. This computation accounts for the underlying
        symmetries of the reference frame as encoded in :code:`equiv_quats`.

        Args:
            box (:class:`freud.box.Box`):
                Simulation box.
            proj_vecs ((:math:`N_{vectors}`, 3) :class:`numpy.ndarray`):
                The set of reference vectors, defined in the reference
                particles' reference frame, to calculate maximal local bond
                projections onto.
            ref_points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`):
                Reference points used in the calculation.
            ref_orientations ((:math:`N_{particles}`, 4) :class:`numpy.ndarray`):
                Reference orientations used in the calculation.
            points ((:math:`N_{particles}`, 3) :class:`numpy.ndarray`, optional):
                Points (neighbors of :code:`ref_points`) used in the
                calculation. Uses :code:`ref_points` if not provided or
                :code:`None`.
                (Default value = :code:`None`).
            equiv_quats ((:math:`N_{quats}`, 4) :class:`numpy.ndarray`, optional):
                The set of all equivalent quaternions that takes the particle
                as it is defined to some global reference orientation. Note
                that this does not need to include both :math:`q` and
                :math:`-q`, since :math:`q` and :math:`-q` effect the same
                rotation on vectors. (Default value = :code:`[1, 0, 0, 0]`)
                (Default value = :code:`None`).
            nlist (:class:`freud.locality.NeighborList`, optional):
                NeighborList to use to find bonds (Default value =
                :code:`None`).
        """  # noqa: E501
        cdef freud.box.Box b = freud.common.convert_box(box)
        ref_points = freud.common.convert_array(ref_points, shape=(None, 3))
        ref_orientations = freud.common.convert_array(
            ref_orientations, shape=(None, 4))

        exclude_ii = points is None
        if points is None:
            points = ref_points
        points = freud.common.convert_array(points, shape=(None, 3))
        equiv_quats = freud.common.convert_array(equiv_quats, shape=(None, 4))
        proj_vecs = freud.common.convert_array(proj_vecs, shape=(None, 3))

        defaulted_nlist = freud.locality.make_default_nlist_nn(
            box, ref_points, points, self.num_neigh, nlist,
            exclude_ii, self.r_max)
        self.nlist_ = defaulted_nlist[0].copy()

        cdef const float[:, ::1] l_ref_points = ref_points
        cdef const float[:, ::1] l_ref_orientations = ref_orientations
        cdef const float[:, ::1] l_points = points
        cdef const float[:, ::1] l_equiv_quats = equiv_quats
        cdef const float[:, ::1] l_proj_vecs = proj_vecs

        cdef unsigned int nRef = l_ref_points.shape[0]
        cdef unsigned int nP = l_points.shape[0]
        cdef unsigned int nEquiv = l_equiv_quats.shape[0]
        cdef unsigned int nProj = l_proj_vecs.shape[0]

        with nogil:
            self.thisptr.compute(
                dereference(b.thisptr),
                self.nlist_.get_ptr(),
                <vec3[float]*> &l_points[0, 0],
                <vec3[float]*> &l_ref_points[0, 0],
                <quat[float]*> &l_ref_orientations[0, 0],
                <quat[float]*> &l_equiv_quats[0, 0],
                <vec3[float]*> &l_proj_vecs[0, 0],
                nP, nRef, nEquiv, nProj)
        return self

    @Compute._computed_property()
    def projections(self):
        cdef unsigned int n_bond_projections = \
            len(self.nlist) * self.thisptr.getNproj()
        if not n_bond_projections:
            return np.asarray([], dtype=np.float32)
        cdef const float[::1] projections = \
            <float[:n_bond_projections]> self.thisptr.getProjections().get()
        return np.asarray(projections)

    @Compute._computed_property()
    def normed_projections(self):
        cdef unsigned int n_bond_projections = \
            len(self.nlist) * self.thisptr.getNproj()
        if not n_bond_projections:
            return np.asarray([], dtype=np.float32)
        cdef const float[::1] normed_projections = \
            <float[:n_bond_projections]> \
            self.thisptr.getNormedProjections().get()
        return np.asarray(normed_projections)

    @Compute._computed_property()
    def num_particles(self):
        return self.thisptr.getNP()

    @Compute._computed_property()
    def num_reference_particles(self):
        return self.thisptr.getNref()

    @Compute._computed_property()
    def num_proj_vectors(self):
        return self.thisptr.getNproj()

    @Compute._computed_property()
    def box(self):
        return freud.box.BoxFromCPP(<freud._box.Box> self.thisptr.getBox())

    def __repr__(self):
        return ("freud.environment.{cls}(r_max={r_max}, "
                "num_neighbors={num_neigh})").format(cls=type(self).__name__,
                                                     r_max=self.r_max,
                                                     num_neigh=self.num_neigh)

    def __str__(self):
        return repr(self)
