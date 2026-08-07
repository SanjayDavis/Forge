// Proof #3: C++ expression parser — token definitions.
#ifndef EXPR_TOKEN_H
#define EXPR_TOKEN_H

#include <cstddef>
#include <string>

namespace expr {

enum class TokenKind {
    Number, Identifier,
    Plus, Minus, Star, Slash, Caret, Percent,
    LParen, RParen, Comma,
    End, Error
};

struct Token {
    TokenKind kind;
    std::string text;
    std::size_t pos;
};

inline const char* token_kind_name(TokenKind k) {
    switch (k) {
        case TokenKind::Number:     return "Number";
        case TokenKind::Identifier: return "Identifier";
        case TokenKind::Plus:       return "Plus";
        case TokenKind::Minus:      return "Minus";
        case TokenKind::Star:       return "Star";
        case TokenKind::Slash:      return "Slash";
        case TokenKind::Caret:      return "Caret";
        case TokenKind::Percent:    return "Percent";
        case TokenKind::LParen:     return "LParen";
        case TokenKind::RParen:     return "RParen";
        case TokenKind::Comma:      return "Comma";
        case TokenKind::End:        return "End";
        case TokenKind::Error:      return "Error";
    }
    return "?";
}

} // namespace expr

#endif // EXPR_TOKEN_H
