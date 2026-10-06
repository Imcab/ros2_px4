// imu_listener: prints the Pixhawk gyroscope from /fmu/out/sensor_combined.
//
// Skeleton only: it builds and spins an empty node. To implement:
//   1. Subscription to px4_msgs::msg::SensorCombined on /fmu/out/sensor_combined
//      with a best-effort QoS (PX4 publishes best effort; the default reliable
//      QoS silently receives nothing).
//   2. Keep the latest gyro_rad[3] (FRD body frame, rad/s) from the callback.
//   3. A timer that prints it at a fixed rate instead of on every message
//      (sensor_combined arrives at hundreds of Hz).
//   4. Parameters: print rate, units (rad/s or deg/s), topic name.

#include <memory>

#include "rclcpp/rclcpp.hpp"

class ImuListener : public rclcpp::Node
{
public:
  ImuListener()
  : Node("imu_listener")
  {
    RCLCPP_INFO(get_logger(), "imu_listener started");
  }
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ImuListener>());
  rclcpp::shutdown();
  return 0;
}
