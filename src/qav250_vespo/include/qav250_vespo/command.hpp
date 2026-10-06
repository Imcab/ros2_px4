#pragma once
// =============================================================================
// Command: la clase base de todo lo que hace el dron, igual que en WPILib.
//
//   initialize()  una vez, al empezar
//   execute()     en cada ciclo mientras corre
//   isFinished()  en cada ciclo: ¿ya terminé?
//   end()         una vez, al terminar
//
// No sabe nada de PX4: los commands concretos (GoTo, Wait) reciben un Vehicle&.
// Solo es un header: no hay command.cpp.
// =============================================================================

namespace qav250_vespo
{

// TODO 3: declara la clase abstracta Command.
//
//   - destructor virtual por defecto:  virtual ~Command() = default;
//     (OBLIGATORIO en una clase base que se borra por puntero: si falta,
//      el destructor de la clase hija no se llama)
//   - virtual void initialize() {}       (vacíos por defecto: cada hijo
//   - virtual void execute() {}           sobreescribe solo los que necesita)
//   - virtual bool isFinished() = 0;     (= 0 -> "puro": cada hijo DEBE darlo)
//   - virtual void end() {}
//
//   En Python esto sería una clase con @abstractmethod.

}  // namespace qav250_vespo
