#include "rclcpp/rclcpp.hpp" // client wrapper de ros
#include "px4_msgs/msg/vehicle_status.hpp"
#include "px4_msgs/msg/vehicle_local_position.hpp"

#include "px4_msgs/msg/offboard_control_mode.hpp"
#include "px4_msgs/msg/trajectory_setpoint.hpp"
#include "px4_msgs/msg/vehicle_command.hpp"

using px4_msgs::msg::OffboardControlMode;
using px4_msgs::msg::TrajectorySetpoint;
using px4_msgs::msg::VehicleCommand;

using px4_msgs::msg::VehicleStatus;
using px4_msgs::msg::VehicleLocalPosition;

using namespace std::chrono_literals;

class Coordinate{
    private:
        float x_;
        float y_;
        float z_;
    public:
        Coordinate(float x, float y, float z): x_(x), y_(y), z_(z){}
        float x() const {return x_;}
        float y() const {return y_;}
        float z() const {return z_;}
};

static Coordinate toPX4(Coordinate c){
    return Coordinate(c.x() -4.0f, c.y() -7.0f, -c.z());
}

enum class State { WARMUP, MISSION, LANDING, DONE };

class TMRMission : public rclcpp::Node{
    public:
        TMRMission(): Node("tmr_mission"){
            auto qos = rclcpp::QoS(1).best_effort().transient_local();

            status_sub_ = create_subscription<VehicleStatus>(
                "/fmu/out/vehicle_status_v4", qos,
                [this](const VehicleStatus::SharedPtr msg){
                status_ = *msg;
            });


            position_sub_ = create_subscription<VehicleLocalPosition>(
                "/fmu/out/vehicle_local_position_v1", qos,
                [this](const VehicleLocalPosition::SharedPtr msg){
                position_ = *msg;
                }
            );

            offboard_pub_ = create_publisher<OffboardControlMode>(
                "/fmu/in/offboard_control_mode", qos);

            traj_pub_ = create_publisher<TrajectorySetpoint>(
                "/fmu/in/trajectory_setpoint", qos
            );

            veh_pub_ = create_publisher<VehicleCommand>(
                "/fmu/in/vehicle_command", qos
            );

            timer_ = create_wall_timer(100ms, [this](){loop();});
        }

    private:
        
        State state_ = State::WARMUP;

        rclcpp::TimerBase::SharedPtr timer_;
        rclcpp::Subscription<VehicleStatus>::SharedPtr status_sub_;
        VehicleStatus status_;
        rclcpp::Subscription<VehicleLocalPosition>::SharedPtr position_sub_;
        VehicleLocalPosition position_;

        rclcpp::Publisher<OffboardControlMode>::SharedPtr offboard_pub_;

        rclcpp::Publisher<TrajectorySetpoint>::SharedPtr traj_pub_;

        rclcpp::Publisher<VehicleCommand>::SharedPtr veh_pub_;

        int counter_ = 0;


        VehicleStatus status_;
        VehicleLocalPosition position_;

        uint64_t now_us(){
            return get_clock()->now().nanoseconds() / 1000;
        }

        void loop(){

        }

        void send_command(uint32_t command, float p1 = 0.0f , float p2 = 0.0f){
            VehicleCommand msg{};

            msg.command = command;
            msg.param1 = p1;
            msg.param2 = p2;
            msg.target_system = 1;
            msg.target_component = 1;
            msg.source_system = 1;
            msg.source_component = 1;
            msg.from_external = true;
            msg.timestamp = now_us();
            veh_pub_ -> publish(msg);
        }

        void go_to(Coordinate c){
            Coordinate goal = toPX4(c);
            TrajectorySetpoint msg{};
            msg.position = {goal.x(), goal.y(), goal.z()};
            msg.yaw = 0.0f;
            msg.timestamp = now_us();
            traj_pub_->publish(msg);
        }

};

int main(int argc, char ** argv){
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<TMRMission>());
  rclcpp::shutdown();
  return 0;
}
