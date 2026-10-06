// =============================================================================
// Framework tests that need neither PX4 nor Gazebo: they run in a second.
//   vespo build qav250_vespo
//   colcon test --packages-select qav250_vespo && colcon test-result --verbose
//
// Style: brace initialization everywhere ({}), so the compiler flags any
// narrowing conversion (e.g. a double silently becoming a float).
// =============================================================================

#include <gtest/gtest.h>

#include <Eigen/Core>

#include "qav250_vespo/field_frame.hpp"

using namespace units::literals;
using qav250_vespo::FieldFrame;

namespace
{

constexpr double kTolerance{1e-5};

const FieldFrame kTmrField{0.7_m, 4.0_m};

}  // namespace

// -----------------------------------------------------------------------------
// FieldFrame
// -----------------------------------------------------------------------------

TEST(FieldFrame, SpawnIsNedOrigin)
{
  const Eigen::Vector3f ned{kTmrField.toNed(0.7_m, 4.0_m, 0_m)};

  EXPECT_NEAR(ned.x(), 0.0f, kTolerance);
  EXPECT_NEAR(ned.y(), 0.0f, kTolerance);
  EXPECT_NEAR(ned.z(), 0.0f, kTolerance);
}

TEST(FieldFrame, ToNedBigTunnelEntry)
{
  const Eigen::Vector3f ned{kTmrField.toNed(2.1_m, 2.3_m, 1.25_m)};
  const Eigen::Vector3f expected{-1.7f, 1.4f, -1.25f};

  EXPECT_NEAR(ned.x(), expected.x(), kTolerance);   // north = field y - spawn y
  EXPECT_NEAR(ned.y(), expected.y(), kTolerance);   // east  = field x - spawn x
  EXPECT_NEAR(ned.z(), expected.z(), kTolerance);   // down  = -altitude
}

TEST(FieldFrame, RoundTripReturnsSamePoint)
{
  // toField must undo toNed exactly. Small tunnel exit, a real waypoint.
  const Eigen::Vector3f ned{kTmrField.toNed(4.7_m, 5.7_m, 1.75_m)};
  const Eigen::Vector3f field{kTmrField.toField(ned)};

  EXPECT_NEAR(field.x(), 4.7f, kTolerance);
  EXPECT_NEAR(field.y(), 5.7f, kTolerance);
  EXPECT_NEAR(field.z(), 1.75f, kTolerance);
}

// -----------------------------------------------------------------------------
// TODO 9: Sequence tests, once Command and Sequence exist. Ideas:
//
//   TEST(Sequence, RunsCommandsInOrder)
//     A test command that finishes after N calls to execute() and records
//     its initialize()/end() calls in a shared std::vector<int>. Put 3 of them
//     in a Sequence, call execute() until isFinished() and check the order.
//
//   TEST(Sequence, EmptyFinishesImmediately)
// -----------------------------------------------------------------------------
