// Proof #3: C++ expression parser — lexer.
#ifndef EXPR_LEXER_H
#define EXPR_LEXER_H

#include <string>
#include <vector>

#include "expr/token.h"

namespace expr {

std::vector<Token> lex(const std::string& src);

} // namespace expr

#endif // EXPR_LEXER_H
