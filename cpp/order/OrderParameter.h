// Copyright (c) 2010-2019 The Regents of the University of Michigan
// This file is from the freud project, released under the BSD 3-Clause License.

#ifndef ORDER_PARAMETER_H
#define ORDER_PARAMETER_H

#include <complex>
#include <memory>
#include <ostream>
#include <tbb/tbb.h>

#include "Box.h"
#include "NeighborList.h"
#include "NeighborComputeFunctional.h"
#include "NeighborQuery.h"
#include "VectorMath.h"

/*! \file OrderParameter.h
    \brief Compute the hexatic order parameter for each particle.
*/

namespace freud { namespace order {

//! Compute the hexagonal order parameter for a set of points
/*!
 */
template<typename T> class OrderParameter
{
public:
    //! Constructor
    OrderParameter(T k): m_box(freud::box::Box()), m_Np(0), m_k(k) {}

    //! Destructor
    virtual ~OrderParameter() {}

    //! Get the simulation box
    const box::Box& getBox() const
    {
        return m_box;
    }

    //! Compute the hex order parameter
    template<typename Func>
    void computeGeneral(Func func, const freud::locality::NeighborList* nlist,
                                  const freud::locality::NeighborQuery* points, freud::locality::QueryArgs qargs)
    {
        // Compute the cell list
        m_box = points->getBox();
        unsigned int Np = points->getNRef();

        // Reallocate the output array if it is not the right size
        if (Np != m_Np)
        {
            m_psi_array = std::shared_ptr<std::complex<float>>(new std::complex<float>[Np],
                                                          std::default_delete<std::complex<float>[]>());
        }

        freud::locality::loopOverNeighborsPoint(points, points->getRefPoints(), Np, qargs, nlist, 
        [=](size_t i)
        {
            m_psi_array.get()[i] = 0; return 0;
        }, 
        [=](size_t i, size_t j, float distance, float weight, int data)
        {
            vec3<float> ref = points->getRefPoints()[i];
            // Compute r between the two particles
            vec3<float> delta = m_box.wrap(points->getRefPoints()[j] - ref);

            // Compute psi for neighboring particle
            // (only constructed for 2d)
            m_psi_array.get()[i] += func(delta);
        },
        [=](size_t i, int data)
        {
            m_psi_array.get()[i] /= std::complex<float>(m_k);
        });
        // Save the last computed number of particles
        m_Np = Np;
    }

    T getK()
    {
        return m_k;
    }

    unsigned int getNP()
    {
        return m_Np;
    }


protected:
    box::Box m_box;    //!< Simulation box where the particles belong
    unsigned int m_Np; //!< Last number of points computed
    T m_k;
    std::shared_ptr<std::complex<float>> m_psi_array; //!< psi array computed
};

}; }; // end namespace freud::order

#endif // ORDER_PARAMETER_H
