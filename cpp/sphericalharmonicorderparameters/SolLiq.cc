#include "SolLiq.h"
#include "Cluster.h"
#include <map>
#include <boost/math/special_functions.hpp>

using namespace std;
using namespace boost::python;

namespace freud { namespace sphericalharmonicorderparameters { 
    
SolLiq::SolLiq(const trajectory::Box& box, float rmax, float Qthreshold, unsigned int Sthreshold, unsigned int l)
    :m_box(box), m_rmax(rmax), m_rmax_cluster(rmax), m_lc(box, rmax), m_Qthreshold(Qthreshold), m_Sthreshold(Sthreshold), m_l(l)
    {    
    m_Np = 0;
    if (m_rmax < 0.0f)
        throw invalid_argument("rmax must be positive");
    if (m_Qthreshold < 0.0)
        throw invalid_argument("Dot product cutoff must be nonnegative");
    if (m_Sthreshold < 0)
        throw invalid_argument("Number of solid-like bonds should be positive");
    if (m_l % 2 == 1)
        throw invalid_argument("l should be even!");
    if (m_l == 0) 
        throw invalid_argument("l shouldbe greater than zero!");
    }
    

//Spherical harmonics from boost.  Chooses appropriate l from m_l local var.
void SolLiq::Ylm(const float theta, const float phi, std::vector<std::complex<float> > &Y)
    {
    if(Y.size() != 2*m_l+1) 
        Y.resize(2*m_l+1);
        
    for(int m = - ((int)m_l); m <= (int)m_l; m++)
        //Doc for boost spherical harmonic
        //http://www.boost.org/doc/libs/1_53_0/libs/math/doc/sf_and_dist/html/math_toolkit/special/sf_poly/sph_harm.html
        // theta = colatitude = 0..Pi
        // Phi = azimuthal (longitudinal) 0..2pi).
        Y[m+m_l]= boost::math::spherical_harmonic(m_l, m, theta, phi);
    //for(unsigned int i = 1; i <= m_l; i++)
    //    Y[i+m_l] = Y[-i+m_l];
    }
    
    
//Spherical harmonics! L=6.  Returns m=-6...6 as a std::vector.    
void SolLiq::Y6m(const float theta, const float phi, std::vector<std::complex<float> > &Y) 
    {
    const int l = 6;
    if(Y.size() != 2*l+1) 
        {
        Y.resize(2*l+1);
        }
    const std::complex<float> j = std::complex<float>(0.0,1.0);
        
    float sintheta = sin(theta);
    float costheta = cos(theta);

    //Do exp(m*j*phi) later
    Y[0] = 1.0/64 * sqrt(3003.0/M_PI) * pow(sintheta,6); 
    Y[1] = 3.0/32 * sqrt(1001.0/M_PI) * costheta*pow(sintheta,5);
    Y[2] = 3.0/32 * sqrt(91.0/(2*M_PI)) * pow(sintheta,4)*(11*pow(costheta,2) - 1); 
    Y[3] = 1.0/32 * sqrt(1365.0/M_PI) * pow(sintheta,3)*costheta*(11*pow(costheta,2) - 3); 
    Y[4] = 1.0/64 * sqrt(1365.0/M_PI) * pow(sintheta,2)*(33*pow(costheta,4)-18*pow(costheta,2)+1); 
    Y[5] = 1.0/16 * sqrt(273.0/(2*M_PI)) * sintheta*costheta*(33*pow(costheta,4)-30*pow(costheta,2)+5); 
    Y[6] = 1.0/32 * sqrt(13.0/M_PI) * (231*pow(costheta,6)-315*pow(costheta,4) + 105*pow(costheta,2) - 5);
    Y[7] = -Y[5];
    Y[8] = Y[4];
    Y[9] = -Y[3];
    Y[10] = Y[2];
    Y[11] = -Y[1];
    Y[12] = Y[0];
    // append exponential
    for(int m = -l; m <= l; m++)
        {
        Y[m+l]=Y[m+l]*exp(std::complex<float>(m,0.0)*j*phi);
        }
    }
void SolLiq::Y4m(const float theta, const float phi, std::vector<std::complex<float> > &Y)
    {
    const int l = 4;
    if(Y.size() != 2*l+1)
        {
        Y.resize(2*l+1);
        }
        
    // constants and theta terms
    const std::complex<float> j = std::complex<float>(0.0,1.0);
    Y[0] = 3.0/16 * sqrt(35.0 / (2*M_PI)) * pow(sin(theta),4);
    Y[1] = 3.0/8  * sqrt(35.0 / M_PI)     * cos(theta)*pow(sin(theta),3);
    Y[2] = 3.0/8  * sqrt(5.0  / (2*M_PI)) * (-1+7*pow(cos(theta),2))*pow(sin(theta),2);
    Y[3] = 3.0/8  * sqrt(5.0  / M_PI)     * cos(theta)*sin(theta)*(-3 + 7 * pow(cos(theta),2));
    Y[4] = 3.0/16 / sqrt(M_PI)            * (3 -30 * cos(theta)*cos(theta) + 35*pow(cos(theta),4));
    Y[5] = -Y[3];
    Y[6] = Y[2];
    Y[7] = -Y[1];
    Y[8] = Y[0];

    // append exponential
    for(int m = -l; m <= l; m++)
        {
            std::complex<float> complex_m = std::complex<float>(m,0.0);
            Y[m+l]=Y[m+l]*exp(complex_m*j*phi);
            //std::cout << "m= " << m << " Y=" << Y[m+6] << " " << std::endl;
        }
    //Done.
    }



//Begins calculation of the solid-liq order parameters.
//Note that the SolLiq container class conatins the threshold cutoffs
void SolLiq::compute(const float3 *points, unsigned int Np)
    {
    m_lc.computeCellList(points,Np);
    
    //Initialize Qlmi
    computeClustersQ(points,Np);
    //Determines number of solid or liquid like bonds
    computeClustersQdot(points,Np);
    //Determines if particles are solid or liquid by clustering those with sufficient solid-like bonds
    computeClustersQS(points,Np);
    m_Np = Np;  
    }
    
//Begins calculation of solliq order parameter.  This variant requires particles to share at least S_threshold neighbors
// in order to cluster them, rather than each possess S_threshold neighbors.    
void SolLiq::computeSolLiqVariant(const float3 *points, unsigned int Np)
    {
    m_lc.computeCellList(points,Np);
    //Initialize Qlmi
    computeClustersQ(points,Np);
    vector< vector<unsigned int> > SolidlikeNeighborlist;
    computeListOfSolidLikeNeighbors(points, Np, SolidlikeNeighborlist);
    computeClustersSharedNeighbors(points, Np, SolidlikeNeighborlist);
    m_Np = Np;     
    }

//Calculate solliq order parameter, without doing normalization.
void SolLiq::computeSolLiqNoNorm(const float3 *points, unsigned int Np)
    {
    m_lc.computeCellList(points,Np);
    //Initialize Qlmi
    computeClustersQ(points,Np);
    //Determines number of solid or liquid like bonds
    computeClustersQdotNoNorm(points,Np);
    //Determines if particles are solid or liquid by clustering those with sufficient solid-like bonds
    computeClustersQS(points,Np);
    m_Np = Np;
    }
    
void SolLiq::computeClustersQ(const float3 *points, unsigned int Np) 
    {
    float rmaxsq = m_rmax * m_rmax;
    if (m_Np != Np) 
        {
        m_Qlmi_array = boost::shared_array<complex<float> >(new complex<float> [(2*m_l+1)*Np]);
        m_number_of_neighbors = boost::shared_array<unsigned int>(new unsigned int[Np]);
        }
    memset((void*)m_Qlmi_array.get(), 0, sizeof(complex<float>)*(2*m_l+1)*Np);
    memset((void*)m_number_of_neighbors.get(), 0, sizeof(unsigned int)*Np);        
    
    
    std::vector<std::complex<float> > Y;  Y.resize(2*m_l+1);
    
    for (unsigned int i = 0; i<Np; i++)
        {
        //get cell point is in
        float3 ref = points[i];
        unsigned int ref_cell = m_lc.getCell(ref);
       
        //loop over neighboring cells
        const std::vector<unsigned int>& neigh_cells = m_lc.getCellNeighbors(ref_cell);
        for (unsigned int neigh_idx = 0; neigh_idx < neigh_cells.size(); neigh_idx++)
            {
            unsigned int neigh_cell = neigh_cells[neigh_idx];
            
            //iterate over particles in neighboring cells
            locality::LinkCell::iteratorcell it = m_lc.itercell(neigh_cell);
            for (unsigned int j = it.next(); !it.atEnd(); j = it.next())
                {
                // rij = rj - ri, from i pointing to j.
                float dx = float(points[j].x - ref.x);
                float dy = float(points[j].y - ref.y);
                float dz = float(points[j].z - ref.z);
                
                float3 delta = m_box.wrap(make_float3(dx, dy, dz));  
                float rsq = delta.x*delta.x + delta.y*delta.y + delta.z*delta.z;

                if (rsq < rmaxsq && i != j)  
                    {                
                    float phi = atan2(delta.y,delta.x);      //0..2Pi
                    float theta = acos(delta.z / sqrt(rsq)); //0..Pi

                    if (m_l == 6)
                        SolLiq::Y6m(theta,phi,Y);
                    else if (m_l == 4)
                        SolLiq::Y4m(theta,phi,Y);
                    else
                        SolLiq::Ylm(theta,phi,Y);
                
                    for(unsigned int k = 0; k < (2*m_l+1); ++k)
                        {
                        m_Qlmi_array[(2*m_l+1)*i+k]+=Y[k];
                        m_number_of_neighbors[i]++;
                        }
                    }
                }//End loop over a particular neighbor cell
            }  //End loops of neighboring cells
        //if (m_number_of_neighbors[i] != 0)
        //    { 
        //    for(unsigned int k = 0; k < (2*m_l+1); ++k)
        //        {
        //        m_Qlmi_array[(2*m_l+1)*i+k]/=m_number_of_neighbors[i];
        //        }
        //    }
        } //Ends loop over particles i for Qlmi calcs}
        
    }   
    
//Initializes Q6lmi, and number of solid-like neighbors per particle.
void SolLiq::computeClustersQdot(const float3 *points, 
                              unsigned int Np)
    {
    //clear vector
    m_qldot_ij.clear();     //Stores all the q dot products between all particles i,j

    // reallocate the cluster_idx array if the size doesn't match the last one    
    if (m_Np != Np) 
        {
        m_number_of_connections = boost::shared_array<unsigned int>(new unsigned int[Np]);
        }

    memset((void*)m_number_of_connections.get(), 0, sizeof(unsigned int)*Np);        
    float rmaxsq = m_rmax * m_rmax;
    uint elements = 2*m_l+1;  //m= -l to l elements
    // for each point
    for (unsigned int i = 0; i < Np; i++)
        {
        // get the cell the point is in
        float3 p = points[i];
        unsigned int cell = m_lc.getCell(p);
        
        // loop over all neighboring cells
        const std::vector<unsigned int>& neigh_cells = m_lc.getCellNeighbors(cell);
        for (unsigned int neigh_idx = 0; neigh_idx < neigh_cells.size(); neigh_idx++)
            {
            unsigned int neigh_cell = neigh_cells[neigh_idx];
            
            // iterate over the particles in that cell
            locality::LinkCell::iteratorcell it = m_lc.itercell(neigh_cell);
            for (unsigned int j = it.next(); !it.atEnd(); j=it.next())
                {
                if (i < j)
                    {
                    // compute r between the two particles
                    float dx = float(p.x - points[j].x);
                    float dy = float(p.y - points[j].y);
                    float dz = float(p.z - points[j].z);
                    float3 delta = m_box.wrap(make_float3(dx, dy, dz));
                    float rsq = delta.x*delta.x + delta.y*delta.y + delta.z*delta.z;

                    if (rsq < rmaxsq)  //Check distance for candidate i,j
                        {
                        //Calc Q dotproduct.
                        std::complex<float> Qdot(0.0,0.0);
                        std::complex<float> Qlminorm(0.0,0.0);//qlmi norm sq
                        std::complex<float> Qlmjnorm(0.0,0.0);
                        for (unsigned int k = 0; k < (elements); ++k)  // loop over m
                            {
                            Qdot += m_Qlmi_array[(elements)*i+k] * conj(m_Qlmi_array[(elements)*j+k]);
                            Qlminorm += m_Qlmi_array[(elements)*i+k]*conj(m_Qlmi_array[(elements)*i+k]);
                            Qlmjnorm += m_Qlmi_array[(elements)*j+k]*conj(m_Qlmi_array[(elements)*j+k]);
                            }
                        Qlminorm = sqrt(Qlminorm);
                        Qlmjnorm = sqrt(Qlmjnorm);
                        Qdot = Qdot/real((Qlminorm*Qlmjnorm));
                        m_qldot_ij.push_back(Qdot);  // Only i < j, other pairs not added.
                        //Check if we're bonded via the threshold criterion
                        if( real(Qdot) > m_Qthreshold) 
                            {
                            //Tick up counts of number of connections these particles have
                            m_number_of_connections[i]++;
                            m_number_of_connections[j]++;
                            }
                        }
                    }
                }
            }
        }
    }

//Initializes Q6lmi, and number of solid-like neighbors per particle.
void SolLiq::computeClustersQdotNoNorm(const float3 *points, 
                              unsigned int Np)
    {
    m_qldot_ij.clear();

    // reallocate the cluster_idx array if the size doesn't match the last one    
    if (m_Np != Np) 
        {
        m_number_of_connections = boost::shared_array<unsigned int>(new unsigned int[Np]);
        }

    memset((void*)m_number_of_connections.get(), 0, sizeof(unsigned int)*Np);        
    float rmaxsq = m_rmax * m_rmax;
    uint elements = 2*m_l+1;
    // for each point
    for (unsigned int i = 0; i < Np; i++)
        {
        // get the cell the point is in
        float3 p = points[i];
        unsigned int cell = m_lc.getCell(p);
        
        // loop over all neighboring cells
        const std::vector<unsigned int>& neigh_cells = m_lc.getCellNeighbors(cell);
        for (unsigned int neigh_idx = 0; neigh_idx < neigh_cells.size(); neigh_idx++)
            {
            unsigned int neigh_cell = neigh_cells[neigh_idx];
            
            // iterate over the particles in that cell
            locality::LinkCell::iteratorcell it = m_lc.itercell(neigh_cell);
            for (unsigned int j = it.next(); !it.atEnd(); j=it.next())
                {
                if (i < j)
                    {
                    // compute r between the two particles
                    float dx = float(p.x - points[j].x);
                    float dy = float(p.y - points[j].y);
                    float dz = float(p.z - points[j].z);
                    float3 delta = m_box.wrap(make_float3(dx, dy, dz));
                    float rsq = delta.x*delta.x + delta.y*delta.y + delta.z*delta.z;

                    if (rsq < rmaxsq)  //Check distance for candidate i,j
                        {
                        //Calc Q dotproduct.
                        std::complex<float> Qdot(0.0,0.0);
                        for (unsigned int k = 0; k < (elements); ++k)  // loop over m
                            {
                            Qdot += m_Qlmi_array[(elements)*i+k] * conj(m_Qlmi_array[(elements)*j+k]);
                            }
                        m_qldot_ij.push_back(Qdot);  // Only i < j, other pairs not added.
                        //Check if we're bonded via the threshold criterion
                        if( real(Qdot) > m_Qthreshold) 
                            {
                            //Tick up counts of number of connections these particles have
                            m_number_of_connections[i]++;
                            m_number_of_connections[j]++;
                            }
                        }
                    }
                }
            }
        }
    }


//Computes the clusters for sol-liq order parameter by using the Sthreshold.
void SolLiq::computeClustersQS(const float3 *points, unsigned int Np)
    {
    if (m_Np != Np) 
        {
        m_cluster_idx = boost::shared_array<unsigned int>(new unsigned int[Np]);
        }
        
    float rmaxcluster_sq = m_rmax_cluster * m_rmax_cluster;
    freud::cluster::DisjointSet dj(Np);
       
    // for each point
    for (unsigned int i = 0; i < Np; i++)
        {
        // get the cell the point is in
        float3 p = points[i];
        unsigned int cell = m_lc.getCell(p);
        
        // loop over all neighboring cells
        const std::vector<unsigned int>& neigh_cells = m_lc.getCellNeighbors(cell);
        for (unsigned int neigh_idx = 0; neigh_idx < neigh_cells.size(); neigh_idx++)
            {
            unsigned int neigh_cell = neigh_cells[neigh_idx];
            
            // iterate over the particles in that cell
            locality::LinkCell::iteratorcell it = m_lc.itercell(neigh_cell);
            for (unsigned int j = it.next(); !it.atEnd(); j=it.next())
                {
                if (i != j)
                    {
                    // compute r between the two particles
                    float dx = float(p.x - points[j].x);
                    float dy = float(p.y - points[j].y);
                    float dz = float(p.z - points[j].z);
                    float3 delta = m_box.wrap(make_float3(dx, dy, dz));
                    float rsq = delta.x*delta.x + delta.y*delta.y + delta.z*delta.z;
                    if (rsq < rmaxcluster_sq && rsq > 1e-6)  //Check distance for candidate i,j
                        {                     
                        if ( (m_number_of_connections[i] >= m_Sthreshold) && (m_number_of_connections[j] >= m_Sthreshold) )
                            {
                            // merge the two sets using the disjoint set
                            uint32_t a = dj.find(i);
                            uint32_t b = dj.find(j);
                            if (a != b)
                                dj.merge(a,b);
                            }
                        }
                    }
                }
            }
        }
    
    // done looping over points. All clusters are now determined. Renumber them from zero to num_clusters-1.
    map<uint32_t, uint32_t> label_map;
    
    // go over every point
    uint32_t cur_set = 0;
    for (uint32_t i = 0; i < Np; i++)
        {
        uint32_t s = dj.find(i);

        // insert it into the mapping if we haven't seen this one yet
        if (label_map.count(s) == 0)
            {
            label_map[s] = cur_set;
            cur_set++;
            }

        // label this point in cluster_idx
        m_cluster_idx[i] = label_map[s];
        }
    
    // cur_set is now the number of clusters
    m_num_clusters = cur_set;
    }

unsigned int SolLiq::getLargestClusterSize()
    {
    std::map<unsigned int, unsigned int> freqcount;
    //m_cluster_idx stores the cluster ID for each particle.  Count by adding to map.
    // Only add if solid like!
    for(unsigned int i = 0; i < m_Np; i++) 
        {
        if(m_number_of_connections[i] >= m_Sthreshold)
            {
            freqcount[m_cluster_idx[i]]++;
            }
        }
    //Traverse map looking for largest cluster size
    unsigned int largestcluster = 0;
    for (std::map<uint,uint>::iterator it=freqcount.begin(); it!=freqcount.end(); ++it) 
        {
        if(it->second > largestcluster)  //Candidate for largest cluster
            {
            largestcluster = it->second;
            }
        }
    return largestcluster;
    }
    
std::vector<unsigned int> SolLiq::getClusterSizes()
    {
    std::map<unsigned int, unsigned int> freqcount;
    //m_cluster_idx stores the cluster ID for each particle.  Count by adding to map.
    for(unsigned int i = 0; i < m_Np; i++) 
        {
        if(m_number_of_connections[i] >= m_Sthreshold)
            {
            freqcount[m_cluster_idx[i]]++;
            }
        else 
            {
            freqcount[m_cluster_idx[i]]=0;
            } 
        }
    //Loop over counting map and shove all cluster sizes into an array
    std::vector<unsigned int> clustersizes;
    for (std::map<uint,uint>::iterator it=freqcount.begin(); it!=freqcount.end(); ++it) 
        {
        clustersizes.push_back(it->second);
        }
    //Sort descending
    std::sort(clustersizes.begin(), clustersizes.end(),std::greater<unsigned int>());
    return clustersizes;
    }

void SolLiq::computeListOfSolidLikeNeighbors(const float3 *points, 
                              unsigned int Np, vector< vector<unsigned int> > &SolidlikeNeighborlist)
    {
    m_qldot_ij.clear();     //Stores all the q dot products between all particles i,j

    //resize
    SolidlikeNeighborlist.resize(Np);
    
    // reallocate the cluster_idx array if the size doesn't match the last one
    
    //These probably don't need allocation each time.
    m_cluster_idx = boost::shared_array<unsigned int>(new unsigned int[Np]);
    m_number_of_connections = boost::shared_array<unsigned int>(new unsigned int[Np]);
    memset((void*)m_number_of_connections.get(), 0, sizeof(unsigned int)*Np);
        
    float rmaxsq = m_rmax * m_rmax;

    // for each point
    for (unsigned int i = 0; i < Np; i++)
        {
        // get the cell the point is in
        float3 p = points[i];
        unsigned int cell = m_lc.getCell(p);
        
        //Empty list
        SolidlikeNeighborlist[i].resize(0);
    
        // loop over all neighboring cells
        const std::vector<unsigned int>& neigh_cells = m_lc.getCellNeighbors(cell);
        for (unsigned int neigh_idx = 0; neigh_idx < neigh_cells.size(); neigh_idx++)
            {
            unsigned int neigh_cell = neigh_cells[neigh_idx];
            
            // iterate over the particles in that cell
            locality::LinkCell::iteratorcell it = m_lc.itercell(neigh_cell);
            for (unsigned int j = it.next(); !it.atEnd(); j=it.next())
                {
                if (i != j)
                    {
                    // compute r between the two particles
                    float dx = float(p.x - points[j].x);
                    float dy = float(p.y - points[j].y);
                    float dz = float(p.z - points[j].z);
                    float3 delta = m_box.wrap(make_float3(dx, dy, dz));
                
                    float rsq = delta.x*delta.x + delta.y*delta.y + delta.z*delta.z;

                    if (rsq < rmaxsq && rsq > 1e-6)  //Check distance for candidate i,j
                        {
                        //Calc Q dotproduct.
                        std::complex<float> Qdot(0.0,0.0);
                        std::complex<float> Qlminorm(0.0,0.0);//qlmi norm sq
                        std::complex<float> Qlmjnorm(0.0,0.0);
                        for (unsigned int k = 0; k < (2*m_l+1); ++k)  // loop over m
                            {
                            //Symmmetry - Could compute Qdot *twice* as fast! (I.e. m=-l and m=+l equivalent so some of these calcs redundant)
                            //std::complex<float> temp =  m_Qlmi_array[(2*m_l+1)*i+k] * conj(m_Qlmi_array[(2*m_l+1)*j+k]);
                            //printf("For component k=%d, real=%f, imag=%f\n",k,real(temp),imag(temp));
                            Qdot += m_Qlmi_array[(2*m_l+1)*i+k] * conj(m_Qlmi_array[(2*m_l+1)*j+k]);
                            Qlminorm += m_Qlmi_array[(2*m_l+1)*i+k]*conj(m_Qlmi_array[(2*m_l+1)*i+k]);
                            Qlmjnorm += m_Qlmi_array[(2*m_l+1)*j+k]*conj(m_Qlmi_array[(2*m_l+1)*j+k]);
                            }
                        Qlminorm = sqrt(Qlminorm);
                        Qlmjnorm = sqrt(Qlmjnorm);
                        Qdot = Qdot/(Qlminorm*Qlmjnorm);
                            
                        if(i < j)
                            {
                            m_qldot_ij.push_back(Qdot);
                            }
                        //Check if we're bonded via the threshold criterion
                        if( real(Qdot) > m_Qthreshold) 
                            {
                            m_number_of_connections[i]++;
                            SolidlikeNeighborlist[i].push_back(j);
                            }
                        }
                    }
                }
            }
        }
    }

void SolLiq::computeClustersSharedNeighbors(const float3 *points, 
    unsigned int Np, const vector< vector<unsigned int> > &SolidlikeNeighborlist)
    {
    
    m_cluster_idx = boost::shared_array<unsigned int>(new unsigned int[Np]);
    m_number_of_shared_connections.clear();  //Reset.

    float rmaxcluster_sq = m_rmax_cluster * m_rmax_cluster;
    freud::cluster::DisjointSet dj(Np);
       
    // for each point
    for (unsigned int i = 0; i < Np; i++)
        {
        // get the cell the point is in
        float3 p = points[i];
        unsigned int cell = m_lc.getCell(p);
        
        // loop over all neighboring cells
        const std::vector<unsigned int>& neigh_cells = m_lc.getCellNeighbors(cell);
        for (unsigned int neigh_idx = 0; neigh_idx < neigh_cells.size(); neigh_idx++)
            {
            unsigned int neigh_cell = neigh_cells[neigh_idx];
            
            // iterate over the particles in that cell
            locality::LinkCell::iteratorcell it = m_lc.itercell(neigh_cell);
            for (unsigned int j = it.next(); !it.atEnd(); j=it.next())
                {
                if (i < j)
                    {
                    // compute r between the two particles
                    float dx = float(p.x - points[j].x);
                    float dy = float(p.y - points[j].y);
                    float dz = float(p.z - points[j].z);
                    float3 delta = m_box.wrap(make_float3(dx, dy, dz));
                
                    float rsq = delta.x*delta.x + delta.y*delta.y + delta.z*delta.z;
                    if (rsq < rmaxcluster_sq && rsq > 1e-6)  //Check distance for candidate i,j
                        {
                        unsigned int num_shared = 0;
                        map<unsigned int, unsigned int> sharedneighbors;
                        for(unsigned int k = 0; k < SolidlikeNeighborlist[i].size(); k++) 
                            {
                            sharedneighbors[SolidlikeNeighborlist[i][k]]++;
                            }
                        for(unsigned int k = 0; k < SolidlikeNeighborlist[j].size(); k++)
                            {
                            sharedneighbors[SolidlikeNeighborlist[j][k]]++;
                            }
                        //Scan through counting number of shared neighbors in the map
                        std::map<unsigned int, unsigned int>::const_iterator it;
                        for(it = sharedneighbors.begin(); it != sharedneighbors.end(); ++it)
                            {
                            if((*it).second>=2)
                                {
                                num_shared++;
                                }
                            }
                        m_number_of_shared_connections.push_back(num_shared);
                        if(num_shared > m_Sthreshold)
                            {
                            // merge the two sets using the disjoint set
                            uint32_t a = dj.find(i);
                            uint32_t b = dj.find(j);
                            if (a != b)
                                dj.merge(a,b);
                            }
                        }
                    }
                }
            }
        }
    
    // done looping over points. All clusters are now determined. Renumber them from zero to num_clusters-1.
    map<uint32_t, uint32_t> label_map;
    
    // go over every point
    uint32_t cur_set = 0;
    for (uint32_t i = 0; i < Np; i++)
        {
        uint32_t s = dj.find(i);

        // insert it into the mapping if we haven't seen this one yet
        if (label_map.count(s) == 0)
            {
            label_map[s] = cur_set;
            cur_set++;
            }

        // label this point in cluster_idx
        m_cluster_idx[i] = label_map[s];
        }
    
    // cur_set is now the number of clusters
    m_num_clusters = cur_set;
    }
  
void SolLiq::computePy(boost::python::numeric::array points)
    {
    //validate input type and rank
    num_util::check_type(points, PyArray_FLOAT);
    num_util::check_rank(points, 2);
    
    // validate that the 2nd dimension is only 3
    num_util::check_dim(points, 1, 3);
    unsigned int Np = num_util::shape(points)[0];
    
    // get the raw data pointers and compute the cell list
    float3* points_raw = (float3*) num_util::data(points);
    compute(points_raw, Np);
    }
    
void SolLiq::computeSolLiqVariantPy(boost::python::numeric::array points)
    {
    //validate input type and rank
    num_util::check_type(points, PyArray_FLOAT);
    num_util::check_rank(points, 2);
    
    // validate that the 2nd dimension is only 3
    num_util::check_dim(points, 1, 3);
    unsigned int Np = num_util::shape(points)[0];
    
    // get the raw data pointers and compute the cell list
    float3* points_raw = (float3*) num_util::data(points);
    computeSolLiqVariant(points_raw, Np);
    }
   
void SolLiq::computeSolLiqNoNormPy(boost::python::numeric::array points)
    {
    //validate input type and rank
    num_util::check_type(points, PyArray_FLOAT);
    num_util::check_rank(points, 2);
    
    // validate that the 2nd dimension is only 3
    num_util::check_dim(points, 1, 3);
    unsigned int Np = num_util::shape(points)[0];
    
    // get the raw data pointers and compute the cell list
    float3* points_raw = (float3*) num_util::data(points);
    computeSolLiqNoNorm(points_raw, Np);
    }
   
void SolLiq::computeNoNormVectorInputPy(boost::python::api::object &pyobj) {
    std::vector<Scalar3> vec = boost::python::extract<std::vector<Scalar3> >(pyobj);
    computeSolLiqNoNorm( (float3*) &vec.front(),vec.size());
}
 
void export_SolLiq()
    {
    class_<SolLiq>("SolLiq", init<trajectory::Box&, float,float,unsigned int, unsigned int>())
        //.def("getBox", &SolLiq::getBox, return_internal_reference<>())
        .def("compute", &SolLiq::computePy)
        .def("computeSolLiqVariant", &SolLiq::computeSolLiqVariantPy)
        .def("computeSolLiqNoNorm", &SolLiq::computeSolLiqNoNormPy)
        .def("computeNoNormVectorInput", &SolLiq::computeNoNormVectorInputPy)
        .def("setClusteringRadius", &SolLiq::setClusteringRadius)
        .def("setBox", &SolLiq::setBox)
        .def("getQlmi", &SolLiq::getQlmiPy)
        .def("getClusters", &SolLiq::getClustersPy)
        .def("getNumberOfConnections",&SolLiq::getNumberOfConnectionsPy)
        .def("getNumberOfSharedConnections",&SolLiq::getNumberOfSharedConnectionsPy)
        .def("getQldot_ij",&SolLiq::getQldot_ijPy)
        .def("calcY4m", &SolLiq::calcY4mPy)
        .def("calcY6m", &SolLiq::calcY6mPy)
        .def("calcYlm", &SolLiq::calcYlmPy)
        .def("getLargestClusterSize",&SolLiq::getLargestClusterSize)
        .def("getClusterSizes",&SolLiq::getClusterSizesPy);
    }


    
}; };// end namespace freud::sol_liq;


