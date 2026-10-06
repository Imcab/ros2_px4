#pragma once
// =============================================================================
// TmrExecutor: encadena la misión completa usando modos OFICIALES de PX4:
//
//   takeoff (de PX4) -> TmrMode (el tuyo) -> land (de PX4) -> esperar desarmado
//
// Cada paso recibe un callback que se llama cuando termina, con un Result
// (Success si salió bien). Es como .andThen() en FRC.
// El executor se activa seleccionando TmrMode en QGC o con un VehicleCommand.
//
// Ejemplo oficial en el que se basa:
//   src/px4-ros2-interface-lib/examples/cpp/modes/mode_with_executor/include/mode.hpp
// =============================================================================

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/components/mode_executor.hpp>
#include <rclcpp/rclcpp.hpp>

namespace qav250_vespo
{

// TODO 7: declara TmrExecutor, que hereda de px4_ros2::ModeExecutorBase.
//
//   Constructor:  explicit TmrExecutor(px4_ros2::ModeBase & owned_mode);
//     - padre: ModeExecutorBase(px4_ros2::ModeExecutorBase::Settings{}, owned_mode)
//     - guarda node_ = owned_mode.node()   (rclcpp::Node &, para logs)
//
//   Igual que el ejemplo oficial, usa un enum de estados y un runState():
//     enum class State { TakingOff, Mission, Landing, WaitUntilDisarmed };
//     void runState(State state, px4_ros2::Result previous_result);
//       - si previous_result != Success -> RCLCPP_ERROR y return (aborta)
//       - switch(state):
//           TakingOff:  takeoff([this](px4_ros2::Result r){ runState(State::Mission, r); }, altura);
//           Mission:    scheduleMode(ownedMode().id(), [this](...){ runState(State::Landing, r); });
//           Landing:    land([this](...){ runState(State::WaitUntilDisarmed, r); });
//           WaitUntilDisarmed: waitUntilDisarmed([this](...){ log "misión completa" });
//
//   Sobreescribe:
//     - void onActivate() override             -> runState(State::TakingOff, px4_ros2::Result::Success);
//     - void onDeactivate(DeactivateReason) override   -> nada, o un log
//
//   La altura de despegue: pásala en el constructor o léela de un parámetro
//   (takeoff_altitude en config/tmr_field.yaml).

}  // namespace qav250_vespo
