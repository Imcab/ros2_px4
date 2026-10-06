// =============================================================================
// tmr_mission: ejecutable de la misión del TMR.
//   ros2 launch qav250_vespo tmr_mission.launch.py
// =============================================================================

// TODO 8: el main, igual que el ejemplo oficial
//   (src/px4-ros2-interface-lib/examples/cpp/modes/mode_with_executor/src/main.cpp):
//
//   #include <px4_ros2/components/node_with_mode.hpp>
//   #include <rclcpp/rclcpp.hpp>
//   #include "qav250_vespo/tmr_executor.hpp"
//   #include "qav250_vespo/tmr_mode.hpp"
//
//   using TmrNode = px4_ros2::NodeWithModeExecutor<qav250_vespo::TmrExecutor, qav250_vespo::TmrMode>;
//
//   main: rclcpp::init, rclcpp::spin(std::make_shared<TmrNode>("tmr_mission", false)), rclcpp::shutdown
//   OJO: el nombre "tmr_mission" debe coincidir con el de config/tmr_field.yaml
//   para que se carguen los parámetros.

int main()
{
  return 0;   // borra esto cuando escribas el main de verdad
}
