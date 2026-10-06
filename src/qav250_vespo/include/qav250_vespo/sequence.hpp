#pragma once
// =============================================================================
// Sequence: corre una lista de commands uno tras otro (SequentialCommandGroup).
// Es a su vez un Command, así que se pueden anidar secuencias.
//
// Es exactamente tu switch(state_) de square_mission, pero genérico:
//   el "estado" es el índice del command actual.
// =============================================================================

#include <cstddef>
#include <memory>
#include <vector>

#include "qav250_vespo/command.hpp"

namespace qav250_vespo
{

// TODO 5: declara Sequence, que hereda de Command.
//
//   Atributos:
//     - std::vector<std::unique_ptr<Command>> commands_;
//         unique_ptr = "este puntero es dueño del objeto y lo borra solo".
//         Hace falta puntero porque guardas GoTo, Wait... (tipos distintos)
//         como si fueran Command (polimorfismo).
//     - size_t index_ = 0;      cuál toca
//     - bool started_ = false;  ¿ya llamé initialize() del actual?
//
//   Métodos:
//     - constructor que reciba el vector y lo guarde con std::move
//       (un unique_ptr no se puede copiar, solo mover)
//     - execute():
//         si ya terminó, no hagas nada
//         si el actual no ha empezado -> initialize(), started_ = true
//         execute() del actual
//         si isFinished() del actual -> end(), index_++, started_ = false
//     - isFinished() -> index_ >= commands_.size()
//     - size_t currentIndex() const   (útil para logs: "voy en el paso 3")
//
//   Pregunta: ¿por qué en execute() hay que revisar "si ya terminó" ANTES de
//   tocar commands_[index_]? (es el mismo bug de waypoints_[5] del cuadrado)

}  // namespace qav250_vespo
