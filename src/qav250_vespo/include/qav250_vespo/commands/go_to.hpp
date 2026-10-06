#pragma once
// =============================================================================
// GoTo: lleva el dron a un punto (NED) y termina cuando llegó Y está quieto.
// =============================================================================

#include <Eigen/Core>

#include "qav250_vespo/command.hpp"
#include "qav250_vespo/vehicle.hpp"

namespace qav250_vespo
{

// TODO 4a: declara GoTo, que hereda de Command (public Command).
//
//   Atributos: Vehicle & vehicle_;  Eigen::Vector3f target_;  float tolerance_;
//     (vehicle_ es REFERENCIA (&): no copia el dron, usa el mismo.
//      Las referencias se inicializan en la lista del constructor:
//        GoTo(Vehicle & v, ...) : vehicle_(v), ... {} )
//
//   Sobreescribe (con override):
//     - initialize()  -> vehicle_.setTarget(target_)
//     - isFinished()  -> distancia < tolerance_  Y  velocidad casi cero
//                        (el ejemplo oficial usa velocity.norm() < 0.3;
//                         para gates usa algo más estricto, ej. 0.2)
//
//   ¿Por qué "y quieto"? Si solo miras distancia, pasa por el punto a toda
//   velocidad y el siguiente tramo empieza chueco: malo para entrar a un túnel.

}  // namespace qav250_vespo
