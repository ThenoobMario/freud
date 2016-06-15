#include "TransOrderParameter.h"
#include "ScopedGILRelease.h"

#include <stdexcept>
#include <complex>

using namespace std;
using namespace tbb;

/*! \file TransOrderParameter.h
    \brief Compute the translational order parameter for each particle
*/

namespace freud { namespace order {

TransOrderParameter::TransOrderParameter(float rmax, float k, unsigned int n)
    : m_box(box::Box()), m_rmax(rmax), m_k(k), m_Np(0)
    {
    m_nn = new locality::NearestNeighbors(m_rmax, n==0? (unsigned int) k: n);
    }

TransOrderParameter::~TransOrderParameter()
    {
    delete m_nn;
    }

void TransOrderParameter::compute(box::Box& box, const vec3<float> *points, unsigned int Np)
    {
    // compute the cell list
    m_box = box;
    m_nn->compute(m_box,points,Np,points,Np);
    m_nn->setRMax(m_rmax);

    // reallocate the output array if it is not the right size
    if (Np != m_Np)
        {
        m_dr_array = boost::shared_array<complex<float> >(new complex<float> [Np]);
        }

    // compute the order parameter
    parallel_for(blocked_range<size_t>(0,Np),
        [=] (const blocked_range<size_t>& r)
        {
        float rmaxsq = m_rmax * m_rmax;

        for(size_t i=r.begin(); i!=r.end(); ++i)
            {
            m_dr_array.get()[i] = 0;
            vec3<float> ref = points[i];

            //loop over neighbors
            locality::NearestNeighbors::iteratorneighbor it = m_nn->iterneighbor(i);
            for (unsigned int j = it.begin(); !it.atEnd(); j = it.next())
                {

                //compute r between the two particles
                vec3<float> delta = m_box.wrap(points[j] - ref);

                float rsq = dot(delta, delta);
                if (rsq > 1e-6)
                    {
                    //compute dr for neighboring particle(only constructed for 2d)
                    m_dr_array.get()[i] += complex<float>(delta.x, delta.y);
                    }
                }
            m_dr_array.get()[i] /= complex<float>(m_k);
            }
        });

    // save the last computed number of particles
    m_Np = Np;
    }

}; }; // end namespace freud::order
