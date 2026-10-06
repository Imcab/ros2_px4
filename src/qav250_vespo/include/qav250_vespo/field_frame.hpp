#pragma once

#include <Eigen/Core>
#include <ros2units/ros2units.hpp>

namespace qav250_vespo{

class FieldFrame{

public:
  FieldFrame(units::length::meter_t spawn_x, units::length::meter_t spawn_y);

  Eigen::Vector3f toNed(units::length::meter_t field_x,
                        units::length::meter_t field_y,
                        units::length::meter_t altitude) const;

  Eigen::Vector3f toField(const Eigen::Vector3f & ned) const;

private:
  units::length::meter_t spawn_x_;
  units::length::meter_t spawn_y_;
};

}