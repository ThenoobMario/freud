import numpy as np
import numpy.testing as npt
import freud
import unittest
import warnings
import util
import rowan

from test_managedarray import TestManagedArray


class TestPMFTR12(unittest.TestCase):
    def test_box(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, 0.0], dtype=np.float32)
        max_r = 5.23
        nbins_r = 10
        nbins_t1 = 20
        nbins_t2 = 30
        myPMFT = freud.pmft.PMFTR12(max_r, (nbins_r, nbins_t1, nbins_t2))
        myPMFT.compute((box, points), angles, points, angles, reset=False)
        npt.assert_equal(myPMFT.box, freud.box.Box.square(L))

        # Ensure expected errors are raised
        box = freud.box.Box.cube(L)
        with self.assertRaises(ValueError):
            myPMFT.compute((box, points), angles, reset=False)

    def test_bins(self):
        max_r = 5.23
        nbins_r = 10
        nbins_t1 = 20
        nbins_t2 = 30
        dr = (max_r / float(nbins_r))
        dT1 = (2.0 * np.pi / float(nbins_t1))
        dT2 = (2.0 * np.pi / float(nbins_t2))

        # make sure the radius for each bin is generated correctly
        listR = np.zeros(nbins_r, dtype=np.float32)
        listT1 = np.zeros(nbins_t1, dtype=np.float32)
        listT2 = np.zeros(nbins_t2, dtype=np.float32)

        listR = np.array([dr*(i+1/2) for i in range(nbins_r) if
                          dr*(i+1/2) < max_r])

        for i in range(nbins_t1):
            t = float(i) * dT1
            nextt = float(i + 1) * dT1
            listT1[i] = ((t + nextt) / 2.0)

        for i in range(nbins_t2):
            t = float(i) * dT2
            nextt = float(i + 1) * dT2
            listT2[i] = ((t + nextt) / 2.0)

        myPMFT = freud.pmft.PMFTR12(max_r, (nbins_r, nbins_t1, nbins_t2))

        # Compare expected bins to the info from pmft
        npt.assert_allclose(myPMFT.bin_centers[0], listR, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[1], listT1, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[2], listT2, atol=1e-3)

        npt.assert_equal(nbins_r, myPMFT.nbins[0])
        npt.assert_equal(nbins_t1, myPMFT.nbins[1])
        npt.assert_equal(nbins_t2, myPMFT.nbins[2])

    def test_attribute_access(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.1, 0.0]],
                          dtype=np.float32)
        points.flags['WRITEABLE'] = False
        angles = np.array([0.0, np.pi/2], dtype=np.float32)
        angles.flags['WRITEABLE'] = False
        max_r = 5.23
        nbins = 10

        myPMFT = freud.pmft.PMFTR12(max_r, nbins)

        with self.assertRaises(AttributeError):
            myPMFT.bin_counts
        with self.assertRaises(AttributeError):
            myPMFT.box
        with self.assertRaises(AttributeError):
            myPMFT.pmft

        myPMFT.compute((box, points), angles, points, angles, reset=False)

        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box
        npt.assert_equal(myPMFT.bin_counts.shape, (nbins, nbins, nbins))
        npt.assert_equal(myPMFT.pmft.shape, (nbins, nbins, nbins))

        myPMFT.compute((box, points), angles, points, angles)
        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box

    def test_two_particles(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.1, 0.0]],
                          dtype=np.float32)
        points.flags['WRITEABLE'] = False
        angles = np.array([0.0, np.pi/2], dtype=np.float32)
        angles.flags['WRITEABLE'] = False
        max_r = 5.23
        nbins_r = 10
        nbins_t1 = 20
        nbins_t2 = 30
        dr = (max_r / float(nbins_r))
        dT1 = (2.0 * np.pi / float(nbins_t1))
        dT2 = (2.0 * np.pi / float(nbins_t2))

        # calculation for array idxs
        def get_bin(query_point, point, query_point_angle, point_angle):
            r_ij = point - query_point
            r_bin = np.floor(np.linalg.norm(r_ij) / dr)
            delta_t1 = np.arctan2(r_ij[1], r_ij[0])
            delta_t2 = np.arctan2(-r_ij[1], -r_ij[0])
            t1_bin = np.floor(
                ((point_angle - delta_t1) % (2. * np.pi)) / dT1)
            t2_bin = np.floor(
                ((query_point_angle - delta_t2) % (2. * np.pi)) / dT2)
            return np.array([r_bin, t1_bin, t2_bin], dtype=np.int32)

        correct_bin_counts = np.zeros(shape=(nbins_r, nbins_t1, nbins_t2),
                                      dtype=np.int32)
        bins = get_bin(points[0], points[1], angles[0], angles[1])
        correct_bin_counts[bins[0], bins[1], bins[2]] = 1
        bins = get_bin(points[1], points[0], angles[1], angles[0])
        correct_bin_counts[bins[0], bins[1], bins[2]] = 1
        absoluteTolerance = 0.1

        r_max = max_r
        test_set = util.make_raw_query_nlist_test_set(
            box, points, points, 'ball', r_max, 0, True)
        for nq, neighbors in test_set:
            myPMFT = freud.pmft.PMFTR12(max_r, (nbins_r, nbins_t1, nbins_t2))
            myPMFT.compute(nq, angles, neighbors=neighbors, reset=False)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)
            myPMFT.compute(nq, angles, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

            myPMFT.compute(nq, angles, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

    def test_repr(self):
        max_r = 5.23
        nbins = 10
        myPMFT = freud.pmft.PMFTR12(max_r, nbins)
        self.assertEqual(str(myPMFT), str(eval(repr(myPMFT))))

    def test_points_ne_query_points(self):
        r_max = 2.3
        nbins = 10

        lattice_size = 10
        box = freud.box.Box.square(lattice_size*5)

        points, query_points = util.make_alternating_lattice(
            lattice_size, 0.01, 2)
        orientations = np.array([0]*len(points))
        query_orientations = np.array([0]*len(query_points))

        test_set = util.make_raw_query_nlist_test_set(
            box, points, query_points, "ball", r_max, 0, False)
        for nq, neighbors in test_set:
            pmft = freud.pmft.PMFTR12(r_max, nbins)
            pmft.compute(nq,
                         orientations, query_points,
                         query_orientations, neighbors=neighbors)

            self.assertEqual(np.count_nonzero(np.isinf(pmft.pmft) == 0), 12)
            self.assertEqual(len(np.unique(pmft.pmft)), 3)


class TestPMFTXYT(unittest.TestCase):
    def test_box(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, 0.0], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins_x = 20
        nbins_y = 30
        nbins_t = 40
        myPMFT = freud.pmft.PMFTXYT(max_x, max_y, (nbins_x, nbins_y, nbins_t))
        myPMFT.compute((box, points), angles, points, angles, reset=False)
        npt.assert_equal(myPMFT.box, freud.box.Box.square(L))

        # Ensure expected errors are raised
        box = freud.box.Box.cube(L)
        with self.assertRaises(ValueError):
            myPMFT.compute((box, points), angles, points, angles, reset=False)

    def test_bins(self):
        max_x = 3.6
        max_y = 4.2
        nbins_x = 20
        nbins_y = 30
        nbins_t = 40
        dx = (2.0 * max_x / float(nbins_x))
        dy = (2.0 * max_y / float(nbins_y))
        dT = (2.0 * np.pi / float(nbins_t))

        # make sure the center for each bin is generated correctly
        listX = np.zeros(nbins_x, dtype=np.float32)
        listY = np.zeros(nbins_y, dtype=np.float32)
        listT = np.zeros(nbins_t, dtype=np.float32)

        for i in range(nbins_x):
            x = float(i) * dx
            nextX = float(i + 1) * dx
            listX[i] = -max_x + ((x + nextX) / 2.0)

        for i in range(nbins_y):
            y = float(i) * dy
            nextY = float(i + 1) * dy
            listY[i] = -max_y + ((y + nextY) / 2.0)

        for i in range(nbins_t):
            t = float(i) * dT
            nextt = float(i + 1) * dT
            listT[i] = ((t + nextt) / 2.0)

        myPMFT = freud.pmft.PMFTXYT(max_x, max_y, (nbins_x, nbins_y, nbins_t))

        # Compare expected bins to the info from pmft
        npt.assert_allclose(myPMFT.bin_centers[0], listX, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[1], listY, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[2], listT, atol=1e-3)

        npt.assert_equal(nbins_x, myPMFT.nbins[0])
        npt.assert_equal(nbins_y, myPMFT.nbins[1])
        npt.assert_equal(nbins_t, myPMFT.nbins[2])

    def test_attribute_access(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.1, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, np.pi/2], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins = 20

        myPMFT = freud.pmft.PMFTXYT(max_x, max_y, nbins)

        with self.assertRaises(AttributeError):
            myPMFT.bin_counts
        with self.assertRaises(AttributeError):
            myPMFT.box
        with self.assertRaises(AttributeError):
            myPMFT.pmft

        myPMFT.compute((box, points), angles, points, angles, reset=False)

        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box
        npt.assert_equal(myPMFT.bin_counts.shape, (nbins, nbins, nbins))
        npt.assert_equal(myPMFT.pmft.shape, (nbins, nbins, nbins))

        myPMFT.compute((box, points), angles, points, angles)
        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box

    def test_two_particles(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.1, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, np.pi/2], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins_x = 20
        nbins_y = 30
        nbins_t = 40
        dx = (2.0 * max_x / float(nbins_x))
        dy = (2.0 * max_y / float(nbins_y))
        dT = (2.0 * np.pi / float(nbins_t))

        # calculation for array idxs
        def get_bin(query_point, point, query_point_angle, point_angle):
            r_ij = point - query_point
            orientation = rowan.from_axis_angle([0, 0, 1], -point_angle)
            rot_r_ij = rowan.rotate(orientation, r_ij)
            xy_bins = np.floor((rot_r_ij[:2] + [max_x, max_y]) /
                               [dx, dy]).astype(np.int32)
            angle_bin = np.floor(
                ((query_point_angle - np.arctan2(-r_ij[1], -r_ij[0])) %
                 (2. * np.pi)) / dT).astype(np.int32)
            return [xy_bins[0], xy_bins[1], angle_bin]

        correct_bin_counts = np.zeros(shape=(nbins_x, nbins_y, nbins_t),
                                      dtype=np.int32)
        bins = get_bin(points[0], points[1], angles[0], angles[1])
        correct_bin_counts[bins[0], bins[1], bins[2]] = 1
        bins = get_bin(points[1], points[0], angles[1], angles[0])
        correct_bin_counts[bins[0], bins[1], bins[2]] = 1
        absoluteTolerance = 0.1

        r_max = np.sqrt(max_x**2 + max_y**2)
        test_set = util.make_raw_query_nlist_test_set(
            box, points, points, 'ball', r_max, 0, True)
        for nq, neighbors in test_set:
            myPMFT = freud.pmft.PMFTXYT(max_x, max_y,
                                        (nbins_x, nbins_y, nbins_t))
            myPMFT.compute(nq, angles, neighbors=neighbors, reset=False)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)
            myPMFT.compute(nq, angles, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

            myPMFT.compute(nq, angles, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

    def test_repr(self):
        max_x = 3.0
        max_y = 4.0
        nbins = 20
        myPMFT = freud.pmft.PMFTXYT(max_x, max_y, nbins)
        self.assertEqual(str(myPMFT), str(eval(repr(myPMFT))))

    def test_points_ne_query_points(self):
        x_max = 2.5
        y_max = 2.5
        n_x = 10
        n_y = 10
        n_t = 4

        lattice_size = 10
        box = freud.box.Box.square(lattice_size*5)

        points, query_points = util.make_alternating_lattice(
            lattice_size, 0.01, 2)
        orientations = np.array([0]*len(points))
        query_orientations = np.array([0]*len(query_points))

        r_max = np.sqrt(x_max**2 + y_max**2)
        test_set = util.make_raw_query_nlist_test_set(
            box, points, query_points, 'ball', r_max, 0, False)

        for nq, neighbors in test_set:
            pmft = freud.pmft.PMFTXYT(x_max, y_max, (n_x, n_y, n_t))
            pmft.compute(nq,
                         orientations, query_points,
                         query_orientations, neighbors=neighbors)

            # when rotated slightly, for each ref point, each quadrant
            # (corresponding to two consecutive bins) should contain 3 points.
            for i in range(n_t):
                self.assertEqual(
                    np.count_nonzero(np.isinf(pmft.pmft[..., i]) == 0), 3)

            self.assertEqual(len(np.unique(pmft.pmft)), 2)


class TestPMFTXY(unittest.TestCase):
    def test_box(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, 0.0], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins_x = 100
        nbins_y = 110
        myPMFT = freud.pmft.PMFTXY(max_x, max_y, (nbins_x, nbins_y))
        myPMFT.compute((box, points), angles, points, reset=False)
        npt.assert_equal(myPMFT.box, freud.box.Box.square(L))

        # Ensure expected errors are raised
        box = freud.box.Box.cube(L)
        with self.assertRaises(ValueError):
            myPMFT.compute((box, points), angles, points, reset=False)

    def test_bins(self):
        max_x = 3.6
        max_y = 4.2
        nbins_x = 20
        nbins_y = 30
        dx = (2.0 * max_x / float(nbins_x))
        dy = (2.0 * max_y / float(nbins_y))

        # make sure the center for each bin is generated correctly
        listX = np.zeros(nbins_x, dtype=np.float32)
        listY = np.zeros(nbins_y, dtype=np.float32)

        for i in range(nbins_x):
            x = float(i) * dx
            nextX = float(i + 1) * dx
            listX[i] = -max_x + ((x + nextX) / 2.0)

        for i in range(nbins_y):
            y = float(i) * dy
            nextY = float(i + 1) * dy
            listY[i] = -max_y + ((y + nextY) / 2.0)

        myPMFT = freud.pmft.PMFTXY(max_x, max_y, (nbins_x, nbins_y))

        # Compare expected bins to the info from pmft
        npt.assert_allclose(myPMFT.bin_centers[0], listX, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[1], listY, atol=1e-3)

        npt.assert_equal(nbins_x, myPMFT.nbins[0])
        npt.assert_equal(nbins_y, myPMFT.nbins[1])

    def test_attribute_access(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, 0.0], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins = 100

        myPMFT = freud.pmft.PMFTXY(max_x, max_y, nbins)

        with self.assertRaises(AttributeError):
            myPMFT.bin_counts
        with self.assertRaises(AttributeError):
            myPMFT.box
        with self.assertRaises(AttributeError):
            myPMFT.pmft

        myPMFT.compute((box, points), angles, points, reset=False)

        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box
        npt.assert_equal(myPMFT.bin_counts.shape, (nbins, nbins))
        npt.assert_equal(myPMFT.pmft.shape, (nbins, nbins))

        myPMFT.compute((box, points), angles, points)
        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box

    def test_two_particles(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, 0.0], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins_x = 100
        nbins_y = 110
        dx = (2.0 * max_x / float(nbins_x))
        dy = (2.0 * max_y / float(nbins_y))

        correct_bin_counts = np.zeros(shape=(nbins_x, nbins_y), dtype=np.int32)

        # calculation for array idxs
        def get_bin(query_point, point):
            return np.floor((query_point - point + [max_x, max_y, 0]) /
                            [dx, dy, 1]).astype(np.int32)[:2]

        bins = get_bin(points[0], points[1])
        correct_bin_counts[bins[0], bins[1]] = 1
        bins = get_bin(points[1], points[0])
        correct_bin_counts[bins[0], bins[1]] = 1
        absoluteTolerance = 0.1

        r_max = np.sqrt(max_x**2 + max_y**2)
        test_set = util.make_raw_query_nlist_test_set(
            box, points, points, 'ball', r_max, 0, True)
        for nq, neighbors in test_set:
            myPMFT = freud.pmft.PMFTXY(max_x, max_y, (nbins_x, nbins_y))
            myPMFT.compute(nq, angles, neighbors=neighbors, reset=False)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)
            myPMFT.compute(nq, angles, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

            myPMFT.compute(nq, angles, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

    def test_repr(self):
        max_x = 3.0
        max_y = 4.0
        nbins = 100
        myPMFT = freud.pmft.PMFTXY(max_x, max_y, nbins)
        self.assertEqual(str(myPMFT), str(eval(repr(myPMFT))))

    def test_repr_png(self):
        L = 16.0
        box = freud.box.Box.square(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        angles = np.array([0.0, 0.0], dtype=np.float32)
        max_x = 3.6
        max_y = 4.2
        nbins_x = 100
        nbins_y = 110
        myPMFT = freud.pmft.PMFTXY(max_x, max_y, (nbins_x, nbins_y))

        with self.assertRaises(AttributeError):
            myPMFT.plot()
        self.assertEqual(myPMFT._repr_png_(), None)

        myPMFT.compute((box, points), angles, points, reset=False)
        myPMFT._repr_png_()

    def test_points_ne_query_points(self):
        x_max = 2.5
        y_max = 2.5
        nbins = 20

        lattice_size = 10
        box = freud.box.Box.square(lattice_size*5)

        points, query_points = util.make_alternating_lattice(
            lattice_size, 0.01, 2)

        query_orientations = np.array([0]*len(query_points))

        r_max = np.sqrt(x_max**2 + y_max**2)
        test_set = util.make_raw_query_nlist_test_set(
            box, points, query_points, 'ball', r_max, 0, False)

        for nq, neighbors in test_set:
            pmft = freud.pmft.PMFTXY(x_max, y_max, nbins)
            pmft.compute(
                nq, query_orientations, query_points, neighbors)

            self.assertEqual(np.count_nonzero(np.isinf(pmft.pmft) == 0), 12)
            self.assertEqual(len(np.unique(pmft.pmft)), 2)

    def test_query_args_nn(self):
        """Test that using nn based query args works."""
        L = 8
        box = freud.box.Box.square(L)
        points = np.array([[0, 0, 0]],
                          dtype=np.float32)
        query_points = np.array([[1.1, 0.0, 0.0],
                                [-1.2, 0.0, 0.0],
                                [0.0, 1.3, 0.0],
                                [0.0, -1.4, 0.0]],
                                dtype=np.float32)
        angles = np.array([0.0]*points.shape[0], dtype=np.float32)
        query_angles = np.array([0.0]*query_points.shape[0], dtype=np.float32)

        max_width = 3
        nbins = 3
        pmft = freud.pmft.PMFTXY(max_width, max_width, nbins)
        pmft.compute((box, points), query_angles, query_points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        # Now every point in query_points will find the origin as a neighbor.
        npt.assert_array_equal(
            pmft.bin_counts,
            [[0, 1, 0],
             [1, 0, 1],
             [0, 1, 0]])
        # Now there will be only one neighbor for the single point.
        pmft.compute((box, query_points), angles, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            pmft.bin_counts,
            [[0, 0, 0],
             [0, 0, 0],
             [0, 1, 0]])

    def test_2d_box_3d_points(self):
        """Test that points with z != 0 fail if the box is 2D."""
        L = 10  # Box Dimensions

        box = freud.box.Box.square(L)  # Initialize Box
        points = np.array([[0, 0, 0], [0, 1, 1]])
        angles = np.zeros(points.shape[0])
        max_width = 3
        nbins = 3
        pmft = freud.pmft.PMFTXY(max_width, max_width, nbins)
        with self.assertRaises(ValueError):
            pmft.compute((box, points), angles,
                         neighbors={'mode': 'nearest', 'num_neighbors': 1})

    def test_quaternions(self):
        """Test that using quaternions as angles works."""
        L = 8
        box = freud.box.Box.square(L)
        points = np.array([[0, 0, 0]],
                          dtype=np.float32)
        query_points = np.array([[1.1, 0.0, 0.0],
                                [-1.2, 0.0, 0.0],
                                [0.0, 1.3, 0.0],
                                [0.0, -1.4, 0.0]],
                                dtype=np.float32)
        angles = np.array([0.0]*points.shape[0], dtype=np.float32)
        query_angles = np.array([0.0]*query_points.shape[0], dtype=np.float32)

        orientations = rowan.from_axis_angle([0, 0, 1], angles)
        query_orientations = rowan.from_axis_angle([0, 0, 1], query_angles)

        max_width = 3
        nbins = 3
        pmft = freud.pmft.PMFTXY(max_width, max_width, nbins)
        pmft.compute((box, points), query_orientations, query_points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        # Now every point in query_points will find the origin as a neighbor.
        npt.assert_array_equal(
            pmft.bin_counts,
            [[0, 1, 0],
             [1, 0, 1],
             [0, 1, 0]])
        # Now there will be only one neighbor for the single point.
        pmft.compute((box, query_points), orientations, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            pmft.bin_counts,
            [[0, 0, 0],
             [0, 0, 0],
             [0, 1, 0]])

    def test_orientation_with_query_points(self):
        """The orientations should be associated with the query points if they
        are provided."""
        L = 8
        box = freud.box.Box.square(L)
        # Don't place the points at exactly distances of 0/1 apart to avoid any
        # ambiguity when the distances fall on the bin boundaries.
        points = np.array([[0.1, 0.1, 0]],
                          dtype=np.float32)
        points2 = np.array([[1, 0, 0]],
                           dtype=np.float32)
        angles = np.array([np.deg2rad(0)]*points2.shape[0], dtype=np.float32)

        max_width = 3
        cells_per_unit_length = 4
        nbins = max_width * cells_per_unit_length
        pmft = freud.pmft.PMFTXY(max_width, max_width, nbins)

        # In this case, the only nonzero bin should be in the bin corresponding
        # to dx=-0.9, dy=0.1, which is (4, 6).
        pmft.compute((box, points), angles, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            (4, 6))

        # Now the sets of points are swapped, so dx=0.9, dy=-0.1, which is
        # (7, 5).
        pmft.compute((box, points2), angles, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            (7, 5))

        # Apply a rotation to whichever point is provided as a query_point by
        # 45 degrees (easiest to picture if you think of each point as a
        # square).
        angles = np.array([np.deg2rad(45)]*points2.shape[0], dtype=np.float32)

        # Determine the relative position of the point when points2 is rotated
        # by 45 degrees. Since we're undoing the orientation of the orientation
        # of the particle, we have to conjugate the quaternion.
        quats = rowan.from_axis_angle([0, 0, 1], angles)
        bond_vector = rowan.rotate(rowan.conjugate(quats), points - points2)
        bins = ((bond_vector+max_width)*cells_per_unit_length/2).astype(int)

        pmft.compute((box, points), angles, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            bins.squeeze()[:2])

        # If we swap the order of the points, the angle should no longer
        # matter.
        bond_vector = rowan.rotate(rowan.conjugate(quats), points2 - points)
        bins = ((bond_vector+max_width)*cells_per_unit_length/2).astype(int)

        pmft.compute((box, points2), angles, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            bins.squeeze()[:2])

    def test_orientation_with_fewer_query_points(self):
        """The orientations should be associated with the query points if they
        are provided. Ensure that this works when the number of points and
        query points differ."""
        L = 8
        box = freud.box.Box.square(L)
        # Don't place the points at exactly distances of 0/1 apart to avoid any
        # ambiguity when the distances fall on the bin boundaries.
        points = np.array([[0.1, 0.1, 0], [0.89, 0.89, 0]],
                          dtype=np.float32)
        points2 = np.array([[1, 0, 0]],
                           dtype=np.float32)
        angles = np.array([np.deg2rad(0)]*points.shape[0], dtype=np.float32)
        angles2 = np.array([np.deg2rad(0)]*points2.shape[0], dtype=np.float32)

        def points_to_set(bin_counts):
            """Extract set of unique occupied bins from pmft bin counts."""
            return set(zip(*np.asarray(np.where(bin_counts)).tolist()))

        max_width = 3
        cells_per_unit_length = 4
        nbins = max_width * cells_per_unit_length
        pmft = freud.pmft.PMFTXY(max_width, max_width, nbins)

        # There should be two nonzero bins:
        #     dx=-0.9, dy=0.1: bin (4, 6).
        #     dx=-0.11, dy=0.89: bin (5, 7).
        pmft.compute((box, points), angles2, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 2})
        npt.assert_array_equal(
            points_to_set(pmft.bin_counts),
            set([(4, 6), (5, 7)]))

        # Now the sets of points are swapped, so:
        #     dx=0.9, dy=-0.1: bin (7, 5).
        #     dx=0.11, dy=-0.89: bin (6, 4).
        pmft.compute((box, points2), angles, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 2})
        npt.assert_array_equal(
            points_to_set(pmft.bin_counts),
            set([(7, 5), (6, 4)]))

        # Apply a rotation to whichever point is provided as a query_point by
        # 45 degrees (easiest to picture if you think of each point as a
        # square).
        angles2 = np.array([np.deg2rad(45)]*points2.shape[0], dtype=np.float32)

        # Determine the relative position of the point when points2 is rotated
        # by 45 degrees. Since we're undoing the orientation of the orientation
        # of the particle, we have to conjugate the quaternion.
        quats = rowan.from_axis_angle([0, 0, 1], angles2)
        bond_vector = rowan.rotate(rowan.conjugate(quats), points - points2)
        bins = ((bond_vector+max_width)*cells_per_unit_length/2).astype(int)
        bins = set([tuple(x) for x in bins[:, :2]])

        pmft.compute((box, points), angles2, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 2})
        npt.assert_array_equal(
            points_to_set(pmft.bin_counts),
            bins)


class TestPMFTXYZ(unittest.TestCase):
    def test_box(self):
        L = 25.0
        box = freud.box.Box.cube(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        orientations = np.array([[1, 0, 0, 0], [1, 0, 0, 0]], dtype=np.float32)
        equiv_orientations = np.array([[1, 0, 0, 0]], dtype=np.float32)
        max_x = 5.23
        max_y = 6.23
        max_z = 7.23
        nbins_x = 100
        nbins_y = 110
        nbins_z = 120
        myPMFT = freud.pmft.PMFTXYZ(max_x, max_y, max_z,
                                    (nbins_x, nbins_y, nbins_z))
        myPMFT.compute(system=(box, points), query_orientations=orientations,
                       query_points=points,
                       equiv_orientations=equiv_orientations, reset=False)
        npt.assert_equal(myPMFT.box, freud.box.Box.cube(L))

        # Ensure expected errors are raised
        box = freud.box.Box.square(L)
        with self.assertRaises(ValueError):
            myPMFT.compute((box, points), orientations, points,
                           orientations, reset=False)

    def test_bins(self):
        max_x = 5.23
        max_y = 6.23
        max_z = 7.23
        nbins_x = 100
        nbins_y = 110
        nbins_z = 120
        dx = (2.0 * max_x / float(nbins_x))
        dy = (2.0 * max_y / float(nbins_y))
        dz = (2.0 * max_z / float(nbins_z))

        listX = np.zeros(nbins_x, dtype=np.float32)
        listY = np.zeros(nbins_y, dtype=np.float32)
        listZ = np.zeros(nbins_z, dtype=np.float32)

        for i in range(nbins_x):
            x = float(i) * dx
            nextX = float(i + 1) * dx
            listX[i] = -max_x + ((x + nextX) / 2.0)

        for i in range(nbins_y):
            y = float(i) * dy
            nextY = float(i + 1) * dy
            listY[i] = -max_y + ((y + nextY) / 2.0)

        for i in range(nbins_z):
            z = float(i) * dz
            nextZ = float(i + 1) * dz
            listZ[i] = -max_z + ((z + nextZ) / 2.0)

        myPMFT = freud.pmft.PMFTXYZ(max_x, max_y, max_z,
                                    (nbins_x, nbins_y, nbins_z))

        # Compare expected bins to the info from pmft
        npt.assert_allclose(myPMFT.bin_centers[0], listX, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[1], listY, atol=1e-3)
        npt.assert_allclose(myPMFT.bin_centers[2], listZ, atol=1e-3)

        npt.assert_equal(nbins_x, myPMFT.nbins[0])
        npt.assert_equal(nbins_y, myPMFT.nbins[1])
        npt.assert_equal(nbins_z, myPMFT.nbins[2])

    def test_attribute_access(self):
        L = 25.0
        box = freud.box.Box.cube(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        orientations = np.array([[1, 0, 0, 0], [1, 0, 0, 0]], dtype=np.float32)
        max_x = 5.23
        max_y = 6.23
        max_z = 7.23
        nbins_x = nbins_y = nbins_z = 100

        myPMFT = freud.pmft.PMFTXYZ(max_x, max_y, max_z, nbins_x)

        with self.assertRaises(AttributeError):
            myPMFT.bin_counts
        with self.assertRaises(AttributeError):
            myPMFT.box
        with self.assertRaises(AttributeError):
            myPMFT.pmft

        myPMFT.compute(system=(box, points), query_orientations=orientations,
                       query_points=points, reset=False)

        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box
        npt.assert_equal(myPMFT.bin_counts.shape, (nbins_x, nbins_y, nbins_z))
        npt.assert_equal(myPMFT.pmft.shape, (nbins_x, nbins_y, nbins_z))

        myPMFT.compute((box, points), orientations)
        myPMFT.bin_counts
        myPMFT.pmft
        myPMFT.box

    def test_two_particles(self):
        L = 25.0
        box = freud.box.Box.cube(L)
        points = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                          dtype=np.float32)
        query_orientations = np.array([[1, 0, 0, 0], [1, 0, 0, 0]],
                                      dtype=np.float32)
        max_x = 5.23
        max_y = 6.23
        max_z = 7.23
        nbins_x = 100
        nbins_y = 110
        nbins_z = 120
        dx = (2.0 * max_x / float(nbins_x))
        dy = (2.0 * max_y / float(nbins_y))
        dz = (2.0 * max_z / float(nbins_z))

        correct_bin_counts = np.zeros(shape=(nbins_x, nbins_y, nbins_z),
                                      dtype=np.int32)

        # calculation for array idxs
        def get_bin(query_point, point):
            return np.floor((query_point - point + [max_x, max_y, max_z]) /
                            [dx, dy, dz]).astype(np.int32)

        bins = get_bin(points[0], points[1])
        correct_bin_counts[bins[0], bins[1], bins[2]] = 1
        bins = get_bin(points[1], points[0])
        correct_bin_counts[bins[0], bins[1], bins[2]] = 1
        absoluteTolerance = 0.1

        r_max = np.sqrt(max_x**2 + max_y**2 + max_z**2)
        test_set = util.make_raw_query_nlist_test_set(
            box, points, points, 'ball', r_max, 0, True)
        for nq, neighbors in test_set:
            myPMFT = freud.pmft.PMFTXYZ(
                max_x, max_y, max_z, (nbins_x, nbins_y, nbins_z))
            myPMFT.compute(nq, query_orientations, neighbors=neighbors,
                           reset=False)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)
            myPMFT.compute(nq, query_orientations, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

            # Test equiv_orientations, shape (N_faces, 4)
            equiv_orientations = np.array([[1., 0., 0., 0.]])
            myPMFT.compute(nq, query_orientations, neighbors=neighbors,
                           equiv_orientations=equiv_orientations)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

            # Test without face orientations.
            myPMFT.compute(nq, query_orientations, neighbors=neighbors)
            npt.assert_allclose(myPMFT.bin_counts, correct_bin_counts,
                                atol=absoluteTolerance)

    def test_shift_two_particles_dead_pixel(self):
        points = np.array([[1, 1, 1], [0, 0, 0]], dtype=np.float32)
        query_orientations = np.array([[1, 0, 0, 0], [1, 0, 0, 0]],
                                      dtype=np.float32)
        noshift = freud.pmft.PMFTXYZ(0.5, 0.5, 0.5, 3, shiftvec=[0, 0, 0])
        shift = freud.pmft.PMFTXYZ(0.5, 0.5, 0.5, 3, shiftvec=[1, 1, 1])

        for pm in [noshift, shift]:
            pm.compute((freud.box.Box.cube(3), points), query_orientations)

        # Ignore warnings about NaNs
        warnings.simplefilter("ignore", category=RuntimeWarning)

        # Non-shifted pmft should have no non-inf valued voxels,
        # since the other point is outside the x/y/z max
        infcheck_noshift = np.isfinite(noshift.pmft).sum()
        # Shifted pmft should have one non-inf valued voxel
        infcheck_shift = np.isfinite(shift.pmft).sum()

        npt.assert_equal(infcheck_noshift, 0)
        npt.assert_equal(infcheck_shift, 1)

    def test_repr(self):
        max_x = 5.23
        max_y = 6.23
        max_z = 7.23
        nbins_x = 100
        nbins_y = 110
        nbins_z = 120
        myPMFT = freud.pmft.PMFTXYZ(max_x, max_y, max_z,
                                    (nbins_x, nbins_y, nbins_z))
        self.assertEqual(str(myPMFT), str(eval(repr(myPMFT))))

    def test_query_args_nn(self):
        """Test that using nn based query args works."""
        L = 8
        box = freud.box.Box.cube(L)
        points = np.array([[0, 0, 0]],
                          dtype=np.float32)
        query_points = np.array([[1.1, 0.0, 0.0],
                                [-1.2, 0.0, 0.0],
                                [0.0, 1.3, 0.0],
                                [0.0, -1.4, 0.0],
                                [0.0, 0.0, 1.5],
                                [0.0, 0.0, -1.6]],
                                dtype=np.float32)
        angles = np.array([[1.0, 0.0, 0.0, 0.0]]*points.shape[0],
                          dtype=np.float32)
        query_angles = np.array([[1.0, 0.0, 0.0, 0.0]]*query_points.shape[0],
                                dtype=np.float32)

        max_width = 3
        nbins = 3
        pmft = freud.pmft.PMFTXYZ(max_width, max_width, max_width, nbins)
        pmft.compute((box, points), query_angles, query_points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})

        # Now every point in query_points will find the origin as a neighbor.
        npt.assert_array_equal(
            pmft.bin_counts,
            [[[0, 0, 0],
              [0, 1, 0],
              [0, 0, 0]],
             [[0, 1, 0],
              [1, 0, 1],
              [0, 1, 0]],
             [[0, 0, 0],
              [0, 1, 0],
              [0, 0, 0]]])

        pmft.compute((box, query_points), angles, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        # The only nonzero bin is the right-center bin (zero distance in y, z)
        self.assertEqual(pmft.bin_counts[2, 1, 1], 1)
        self.assertEqual(np.sum(pmft.bin_counts), 1)
        self.assertTrue(np.all(pmft.bin_counts >= 0))

    def test_orientation_with_query_points(self):
        """The orientations should be associated with the query points if they
        are provided."""
        L = 8
        box = freud.box.Box.cube(L)
        # Don't place the points at exactly distances of 0/1 apart to avoid any
        # ambiguity when the distances fall on the bin boundaries.
        points = np.array([[0.1, 0.1, 0]],
                          dtype=np.float32)
        points2 = np.array([[1, 0, 0]],
                           dtype=np.float32)
        angles = np.array([np.deg2rad(0)]*points2.shape[0], dtype=np.float32)
        quats = rowan.from_axis_angle([0, 0, 1], angles)

        max_width = 3
        cells_per_unit_length = 4
        nbins = max_width * cells_per_unit_length
        pmft = freud.pmft.PMFTXYZ(max_width, max_width, max_width, nbins)

        # In this case, the only nonzero bin should be in the bin corresponding
        # to dx=-0.9, dy=0.1, which is (4, 6).
        pmft.compute((box, points), quats, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            (4, 6, 6))

        # Now the sets of points are swapped, so dx=0.9, dy=-0.1, which is
        # (7, 5).
        pmft.compute((box, points2), quats, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            (7, 5, 6))

        # Apply a rotation to whichever point is provided as a query_point by
        # 45 degrees (easiest to picture if you think of each point as a
        # square).
        angles = np.array([np.deg2rad(45)]*points2.shape[0], dtype=np.float32)
        quats = rowan.from_axis_angle([0, 0, 1], angles)

        # Determine the relative position of the point when points2 is rotated
        # by 45 degrees. Since we're undoing the orientation of the orientation
        # of the particle, we have to conjugate the quaternion.
        bond_vector = rowan.rotate(rowan.conjugate(quats), points - points2)
        bins = ((bond_vector+max_width)*cells_per_unit_length/2).astype(int)

        pmft.compute((box, points), quats, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            bins.squeeze())

        # If we swap the order of the points, the angle should no longer
        # matter.
        bond_vector = rowan.rotate(rowan.conjugate(quats), points2 - points)
        bins = ((bond_vector+max_width)*cells_per_unit_length/2).astype(int)

        pmft.compute((box, points2), quats, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 1})
        npt.assert_array_equal(
            np.asarray(np.where(pmft.bin_counts)).squeeze(),
            bins.squeeze())

    def test_orientation_with_fewer_query_points(self):
        """The orientations should be associated with the query points if they
        are provided. Ensure that this works when the number of points and
        query points differ."""
        L = 8
        box = freud.box.Box.cube(L)
        # Don't place the points at exactly distances of 0/1 apart to avoid any
        # ambiguity when the distances fall on the bin boundaries.
        points = np.array([[0.1, 0.1, 0], [0.89, 0.89, 0]],
                          dtype=np.float32)
        points2 = np.array([[1, 0, 0]],
                           dtype=np.float32)
        angles = np.array([np.deg2rad(0)]*points.shape[0], dtype=np.float32)
        quats = rowan.from_axis_angle([0, 0, 1], angles)
        angles2 = np.array([np.deg2rad(0)]*points2.shape[0], dtype=np.float32)
        quats2 = rowan.from_axis_angle([0, 0, 1], angles2)

        def points_to_set(bin_counts):
            """Extract set of unique occupied bins from pmft bin counts."""
            return set(zip(*np.asarray(np.where(bin_counts)).tolist()))

        max_width = 3
        cells_per_unit_length = 4
        nbins = max_width * cells_per_unit_length
        pmft = freud.pmft.PMFTXYZ(max_width, max_width, max_width, nbins)

        # There should be two nonzero bins:
        #     dx=-0.9, dy=0.1: bin (4, 6).
        #     dx=-0.11, dy=0.89: bin (5, 7).
        pmft.compute((box, points), quats2, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 2})
        npt.assert_array_equal(
            points_to_set(pmft.bin_counts),
            set([(4, 6, 6), (5, 7, 6)]))

        # Now the sets of points are swapped, so:
        #     dx=0.9, dy=-0.1: bin (7, 5).
        #     dx=0.11, dy=-0.89: bin (6, 4).
        pmft.compute((box, points2), quats, points,
                     neighbors={'mode': 'nearest', 'num_neighbors': 2})
        npt.assert_array_equal(
            points_to_set(pmft.bin_counts),
            set([(7, 5, 6), (6, 4, 6)]))

        # Apply a rotation to whichever point is provided as a query_point by
        # 45 degrees (easiest to picture if you think of each point as a
        # square).
        angles2 = np.array([np.deg2rad(45)]*points2.shape[0], dtype=np.float32)
        quats2 = rowan.from_axis_angle([0, 0, 1], angles2)

        # Determine the relative position of the point when points2 is rotated
        # by 45 degrees. Since we're undoing the orientation of the orientation
        # of the particle, we have to conjugate the quaternion.
        bond_vector = rowan.rotate(rowan.conjugate(quats2), points - points2)
        bins = ((bond_vector+max_width)*cells_per_unit_length/2).astype(int)
        bins = set([tuple(x) for x in bins])

        pmft.compute((box, points), quats2, points2,
                     neighbors={'mode': 'nearest', 'num_neighbors': 2})
        npt.assert_array_equal(
            points_to_set(pmft.bin_counts),
            bins)


class TestPMFTR12ManagedArray(TestManagedArray, unittest.TestCase):
    def build_object(self):
        self.obj = freud.pmft.PMFTR12(5, (50, 50, 50))

    @property
    def computed_properties(self):
        return ['bin_counts', 'pmft']

    def compute(self):
        box = freud.box.Box.square(10)
        num_points = 100
        points = np.random.rand(
            num_points, 3)*box.L - box.L/2
        angles = np.random.rand(num_points)*2*np.pi
        self.obj.compute((box, points), angles, neighbors={'r_max': 3})


class TestPMFTXYTManagedArray(TestManagedArray, unittest.TestCase):
    def build_object(self):
        self.obj = freud.pmft.PMFTXYT(5, 5, (50, 50, 50))

    @property
    def computed_properties(self):
        return ['bin_counts', 'pmft']

    def compute(self):
        box = freud.box.Box.square(10)
        num_points = 100
        points = np.random.rand(
            num_points, 3)*box.L - box.L/2
        angles = np.random.rand(num_points)*2*np.pi
        self.obj.compute((box, points), angles, neighbors={'r_max': 3})


class TestPMFTXYManagedArray(TestManagedArray, unittest.TestCase):
    def build_object(self):
        self.obj = freud.pmft.PMFTXY(5, 5, (50, 50))

    @property
    def computed_properties(self):
        return ['bin_counts', 'pmft']

    def compute(self):
        box = freud.box.Box.square(10)
        num_points = 100
        points = np.random.rand(
            num_points, 3)*box.L - box.L/2
        angles = np.random.rand(num_points)*2*np.pi
        self.obj.compute((box, points), angles, neighbors={'r_max': 3})


class TestPMFTXYZManagedArray(TestManagedArray, unittest.TestCase):
    def build_object(self):
        self.obj = freud.pmft.PMFTXYZ(5, 5, 5, (50, 50, 50))

    @property
    def computed_properties(self):
        return ['bin_counts', 'pmft']

    def compute(self):
        box = freud.box.Box.cube(10)
        num_points = 100
        points = np.random.rand(
            num_points, 3)*box.L - box.L/2
        orientations = rowan.random.rand(num_points)
        self.obj.compute((box, points), orientations, neighbors={'r_max': 3})


class TestCompare(unittest.TestCase):
    def test_XY_XYZ(self):
        """Check that 2D and 3D PMFTs give the same results."""
        x_max = 2.5
        y_max = 2.5
        z_max = 1
        nbins = 4
        num_points = 100
        L = 10

        box2d = freud.box.Box.square(L)
        box3d = freud.box.Box.cube(L)

        points = np.random.rand(num_points, 3)
        points[:, 2] = 0
        orientations = np.array([[1, 0, 0, 0]]*len(points))

        pmft2d = freud.pmft.PMFTXY(x_max, y_max, nbins)
        pmft2d.compute((box2d, points), orientations)

        pmft3d = freud.pmft.PMFTXYZ(x_max, y_max, z_max, nbins)
        pmft3d.compute((box3d, points), orientations)

        # Bin counts are equal, PMFTs are scaled by the box length in z.
        npt.assert_array_equal(pmft2d.bin_counts,
                               pmft3d.bin_counts[:, :, nbins//2])
        # The numerator of the scale factor comes from the extra z bins (which
        # we cannot avoid adding because of the query distance limitations on
        # NeighborQuery objects). The denominator comes from the 8pi^2 of
        # orientational phase space in PMFTXYZ divided by the 2pi in theta
        # space in PMFTXY.
        scale_factor = ((nbins/2)*L)/(4*np.pi)
        npt.assert_allclose(np.exp(pmft2d.pmft),
                            np.exp(pmft3d.pmft[:, :, nbins//2])*scale_factor,
                            atol=1e-6)

    def test_XY_XYT(self):
        """Check that XY and XYT PMFTs give the same results."""
        x_max = 2.5
        y_max = 2.5
        nbins = 3
        nbinsxyt = (3, 3, 1)
        num_points = 100
        L = 10

        box = freud.box.Box.square(L)

        np.random.seed(0)
        points = np.random.rand(num_points, 3)
        points[:, 2] = 0
        orientations = np.array([0]*len(points))

        pmftxy = freud.pmft.PMFTXY(x_max, y_max, nbins)
        pmftxy.compute((box, points), orientations)

        pmftxyt = freud.pmft.PMFTXYT(x_max, y_max, nbinsxyt)
        pmftxyt.compute((box, points), orientations)

        npt.assert_array_equal(pmftxy.bin_counts,
                               pmftxyt.bin_counts.reshape(nbins, nbins))
        npt.assert_allclose(np.exp(pmftxy.pmft),
                            np.exp(pmftxyt.pmft).reshape(nbins, nbins),
                            atol=1e-6)


if __name__ == '__main__':
    unittest.main()
