// Proof #3: C++ expression parser — precedence-climbing parser.
#ifndef EXPR_PARSER_H
#define EXPR_PARSER_H

#include <memory>
#include <vector>

#include "expr/ast.h"
#include "expr/token.h"

namespace expr {

std::shared_ptr<Node> parse(const std::vector<Token>& tokens);

} // namespace expr

#endif // EXPR_PARSER_H
