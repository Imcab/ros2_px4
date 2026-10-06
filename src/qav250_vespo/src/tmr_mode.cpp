#include "qav250_vespo/tmr_mode.hpp"

#include "qav250_vespo/commands/go_to.hpp"
#include "qav250_vespo/commands/wait.hpp"

namespace qav250_vespo
{

// TODO 6: implementa TmrMode.
//
//   Parámetros que vienen de config/tmr_field.yaml (ver ese archivo):
//     spawn_x, spawn_y            -> FieldFrame
//     tolerance, max_speed
//     waypoints                   -> std::vector<double> plano: [x0, y0, alt0, x1, y1, alt1, ...]
//                                    (ROS 2 no tiene "lista de listas": se aplana y se recorre de 3 en 3)
//     hold_s                      -> std::vector<double>, una espera por waypoint (0 = no esperar)
//
//   En buildMission(): por cada waypoint i
//     GoTo hacia frame.toNed(waypoints[3*i], waypoints[3*i+1], waypoints[3*i+2])
//     si hold_s[i] > 0 -> Wait de hold_s[i] segundos
//   Revisa que waypoints.size() sea múltiplo de 3 y que hold_s tenga uno por waypoint;
//   si no, RCLCPP_ERROR: mejor fallar al arrancar que en el aire.

}  // namespace qav250_vespo
