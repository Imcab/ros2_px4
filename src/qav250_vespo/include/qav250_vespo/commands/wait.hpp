#pragma once
// =============================================================================
// Wait: no hace nada durante un tiempo (el dron se queda en su último objetivo,
// porque Vehicle lo sigue mandando). Sirve para estabilizarse antes de una gate.
// =============================================================================

#include <rclcpp/rclcpp.hpp>

#include "qav250_vespo/command.hpp"

namespace qav250_vespo
{

// TODO 4b: declara Wait, que hereda de Command.
//
//   Atributos: rclcpp::Clock::SharedPtr clock_;  rclcpp::Duration duration_;  rclcpp::Time start_;
//
//   Sobreescribe:
//     - initialize()  -> start_ = clock_->now();
//     - isFinished()  -> clock_->now() - start_ >= duration_
//
//   Ojo: rclcpp::Duration NO tiene constructor por defecto, así que hay que
//   inicializarlo en la lista del constructor. Puedes construirlo desde
//   segundos con rclcpp::Duration::from_seconds(s).
//
//   Usa tiempo real (clock), no contar ciclos como counter_: si el ciclo cambia
//   de 10 Hz a 50 Hz, un contador cambia de duración; el reloj no.

}  // namespace qav250_vespo
