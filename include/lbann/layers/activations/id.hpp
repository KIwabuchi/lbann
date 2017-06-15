////////////////////////////////////////////////////////////////////////////////
// Copyright (c) 2014-2016, Lawrence Livermore National Security, LLC.
// Produced at the Lawrence Livermore National Laboratory.
// Written by the LBANN Research Team (B. Van Essen, et al.) listed in
// the CONTRIBUTORS file. <lbann-dev@llnl.gov>
//
// LLNL-CODE-697807.
// All rights reserved.
//
// This file is part of LBANN: Livermore Big Artificial Neural Network
// Toolkit. For details, see http://software.llnl.gov/LBANN or
// https://github.com/LLNL/LBANN.
//
// Licensed under the Apache License, Version 2.0 (the "Licensee"); you
// may not use this file except in compliance with the License.  You may
// obtain a copy of the License at:
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
// implied. See the License for the specific language governing
// permissions and limitations under the license.
////////////////////////////////////////////////////////////////////////////////

#ifndef ID_HPP_INCLUDED
#define ID_HPP_INCLUDED

#include "lbann/layers/activations/activation.hpp"

namespace lbann {

/** Identity activation function -- does nothing. */
template <data_layout T_layout>
class id_layer : public entrywise_activation_layer {
 public:
  // TODO: Optimize this to copy instead of applying elementwise.
  id_layer(data_layout data_dist, uint index, lbann_comm *comm,
           const uint mini_batch_size, uint num_neurons) :
    entrywise_activation_layer(data_dist, index, comm,
                               mini_batch_size, num_neurons) { initialize_distributed_matrices(); }

  virtual inline void initialize_distributed_matrices() {
    entrywise_activation_layer::initialize_distributed_matrices<T_layout>();
  }

 protected:
  DataType activation_function(DataType z) {
    return z;
  }
  DataType activation_function_gradient(DataType z) {
    return z;
  }
};

}  // namespace lbann

#endif  // ID_HPP_INCLUDED
