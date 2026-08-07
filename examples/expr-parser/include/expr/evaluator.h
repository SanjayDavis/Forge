// Proof #3: C++ expression parser — evaluator.
#ifndef EXPR_EVALUATOR_H
#define EXPR_EVALUATOR_H

#include <memory>

#include "expr/ast.h"
#include "expr/context.h"

namespace expr {

// Evaluate a parsed expression. Throws EvalError on division by zero,
// unknown variables/functions, or bad arity.
double eval(const std::shared_ptr<Node>& node, const Context& ctx);

} // namespace expr

#endif // EXPR_EVALUATOR_H
