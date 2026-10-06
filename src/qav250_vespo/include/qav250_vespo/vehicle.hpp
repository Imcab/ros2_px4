#pragma once
// =============================================================================
// Vehicle: el "subsystem" (como en FRC). Lo único que los commands conocen del dron.
//
// Envuelve las piezas de px4-ros2-interface-lib que el modo crea:
//   - MulticopterGotoSetpointType  -> "ve a esta posición" (con límites de velocidad)
//   - OdometryLocalPosition        -> dónde está y qué tan rápido va (NED)
// Así los commands no dependen de la librería directamente: si mañana cambias
// cómo se manda el setpoint, solo cambia esta clase.
//
// La librería ya manda el heartbeat y maneja offboard/armado: aquí NO hay
// OffboardControlMode ni VehicleCommand como en drone_control.
// =============================================================================

#include <memory>

#include <Eigen/Core>
#include <px4_ros2/control/setpoint_types/multicopter/goto.hpp>
#include <px4_ros2/odometry/local_position.hpp>

namespace qav250_vespo
{

// TODO 2: declara la clase Vehicle.
//
//   Atributos (privados):
//     - std::shared_ptr<px4_ros2::MulticopterGotoSetpointType> goto_;
//     - std::shared_ptr<px4_ros2::OdometryLocalPosition> position_;
//     - Eigen::Vector3f target_  (el último objetivo pedido, para seguir mandándolo)
//     - float max_speed_         (m/s, para cruzar gates despacio)
//
//   Métodos (públicos):
//     - constructor que reciba los dos shared_ptr y la velocidad máxima
//     - void setTarget(const Eigen::Vector3f & ned)       guarda el objetivo
//     - void update()                                     manda target_ con goto_->update(...)
//                                                         (se llama en CADA ciclo, como periodic())
//     - Eigen::Vector3f position() const                  position_->positionNed()
//     - Eigen::Vector3f velocity() const                  position_->velocityNed()
//     - float distanceTo(const Eigen::Vector3f & p) const (p - position()).norm()
//
//   Firma de goto_->update en la librería (los parámetros opcionales al final):
//     update(position, heading, max_horizontal_vel, max_vertical_vel, max_heading_rate)
//   heading, etc. son std::optional<float>: puedes pasar {} para "no me importa".

}  // namespace qav250_vespo
