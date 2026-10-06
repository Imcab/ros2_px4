#include "qav250_vespo/field_frame.hpp"

namespace qav250_vespo{

FieldFrame::FieldFrame(units::length::meter_t spawn_x, units::length::meter_t spawn_y): spawn_x_{spawn_x}, spawn_y_{spawn_y} {}

Eigen::Vector3f FieldFrame::toNed(units::length::meter_t field_x, units::length::meter_t field_y, units::length::meter_t altitude) const{
    return Eigen::Vector3f(
        static_cast<float>((field_y - spawn_y_).value()),
        static_cast<float>((field_x - spawn_x_).value()),
        static_cast<float>(-altitude.value())
    );
}

Eigen::Vector3f FieldFrame::toField(const Eigen::Vector3f & ned) const{

    return Eigen::Vector3f(
        ned.y()  + static_cast<float>(spawn_x_.value()),
        ned.x()  + static_cast<float>(spawn_y_.value()),
        -ned.z()
    );
}

}