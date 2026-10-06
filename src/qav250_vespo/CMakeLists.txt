cmake_minimum_required(VERSION 3.8)
project(qav250_vespo)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(px4_ros2_cpp REQUIRED)
find_package(Eigen3 REQUIRED NO_MODULE)
find_package(ros2units REQUIRED)   # units::meter_t, 10_cm, 1.5_s... (same library as WPILib)

set(DEPENDENCIES rclcpp px4_msgs px4_ros2_cpp)

# ---------------------------------------------------------------------------
# Library: the framework (vehicle, frames, commands, sequence) and the TMR
# mode/executor. Every executable links against it, so a new mission is a new
# small main, not a copy of the framework.
# Add each new .cpp under src/ here.
# ---------------------------------------------------------------------------
add_library(${PROJECT_NAME}
  src/field_frame.cpp
  src/vehicle.cpp
  src/sequence.cpp
  src/commands/go_to.cpp
  src/commands/wait.cpp
  src/tmr_mode.cpp
  src/tmr_executor.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(${PROJECT_NAME} PUBLIC cxx_std_17)
target_link_libraries(${PROJECT_NAME} Eigen3::Eigen ros2units::ros2units)
ament_target_dependencies(${PROJECT_NAME} ${DEPENDENCIES})

# ---------------------------------------------------------------------------
# Executables: one per mission. `ros2 run qav250_vespo tmr_mission`
# ---------------------------------------------------------------------------
add_executable(tmr_mission src/tmr_mission_main.cpp)
target_link_libraries(tmr_mission ${PROJECT_NAME})

install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(TARGETS tmr_mission DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})

# ---------------------------------------------------------------------------
# Tests: framework logic without PX4 or Gazebo. `colcon test --packages-select qav250_vespo`
# ---------------------------------------------------------------------------
if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_framework test/test_framework.cpp)
  target_link_libraries(test_framework ${PROJECT_NAME})
endif()

ament_export_include_directories(include)
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(${DEPENDENCIES} Eigen3 ros2units)
ament_package()
