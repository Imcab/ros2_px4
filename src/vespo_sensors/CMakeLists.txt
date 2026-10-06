cmake_minimum_required(VERSION 3.8)
project(vespo_sensors)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(ros2units REQUIRED)

# Subscribes to /fmu/out/sensor_combined and prints the gyroscope
add_executable(imu_listener src/imu_listener.cpp)
target_compile_features(imu_listener PUBLIC cxx_std_17)
ament_target_dependencies(imu_listener rclcpp px4_msgs)
target_link_libraries(imu_listener ros2units::ros2units)

install(TARGETS imu_listener
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # Not a git repo with a copyright header in every file yet
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
