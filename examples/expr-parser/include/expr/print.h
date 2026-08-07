// Proof #3: C++ expression parser — AST pretty printer.
#ifndef EXPR_PRINT_H
#define EXPR_PRINT_H

#include <memory>
#include <string>

#include "expr/ast.h"

namespace expr {

// S-expression-ish rendering, e.g. Binary(+ 2 (* 3 4)) -> "(+ 2 (* 3 4))".
std::string print_ast(const std::shared_ptr<Node>& node);

} // namespace expr

#endif // EXPR_PRINT_H
