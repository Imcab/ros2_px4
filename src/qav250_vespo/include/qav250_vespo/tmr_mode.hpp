#pragma once
// =============================================================================
// TmrMode: la misión del TMR como MODO DE VUELO de PX4 (forma oficial).
//
// Aparece en QGroundControl como "TMR Gates". PX4 lo activa (o el executor),
// y mientras está activo llama updateSetpoint() periódicamente: ese es tu
// "loop()", donde corre la Sequence. Si alguien cambia de modo desde el control
// o hay un failsafe, PX4 lo desactiva y tu código deja de mandar: seguro.
//
// Ejemplo oficial en el que se basa:
//   src/px4-ros2-interface-lib/examples/cpp/modes/goto/include/mode.hpp
// =============================================================================

#include <memory>

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/multicopter/goto.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <rclcpp/rclcpp.hpp>

#include "qav250_vespo/field_frame.hpp"
#include "qav250_vespo/sequence.hpp"
#include "qav250_vespo/vehicle.hpp"

namespace qav250_vespo
{

// TODO 6: declara TmrMode, que hereda de px4_ros2::ModeBase.
//
//   Constructor:  explicit TmrMode(rclcpp::Node & node);
//     - llama al padre: ModeBase(node, Settings{"TMR Gates"})
//     - crea goto_ y position_ con std::make_shared<...>(*this)   (como el ejemplo)
//     - crea vehicle_ con ellos
//     - lee los parámetros de config/tmr_field.yaml con
//       node.declare_parameter<tipo>("nombre", valor_por_defecto)
//
//   Sobreescribe (override):
//     - void onActivate()            arma una Sequence NUEVA desde los parámetros
//                                    (nueva cada vez: si reactivas el modo, empieza de cero)
//     - void onDeactivate()          nada, o un log
//     - void updateSetpoint(float dt_s)
//          mission_->execute();
//          vehicle_->update();                         (manda el setpoint SIEMPRE)
//          si mission_->isFinished() -> completed(px4_ros2::Result::Success);
//
//   Atributos:
//     - std::shared_ptr<px4_ros2::MulticopterGotoSetpointType> goto_;
//     - std::shared_ptr<px4_ros2::OdometryLocalPosition> position_;
//     - std::unique_ptr<Vehicle> vehicle_;
//     - std::unique_ptr<Sequence> mission_;
//     - los parámetros leídos (FieldFrame, waypoints, tolerancia...)
//
//   Para construir la Sequence (en un método privado, ej. buildMission()):
//     std::vector<std::unique_ptr<Command>> steps;
//     steps.push_back(std::make_unique<GoTo>(*vehicle_, frame.toNed(x, y, alt), tol));
//     steps.push_back(std::make_unique<Wait>(node().get_clock(), ...));
//     mission_ = std::make_unique<Sequence>(std::move(steps));

}  // namespace qav250_vespo
