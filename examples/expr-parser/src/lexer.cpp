// Proof #3: C++ expression parser — lexer implementation.
#include "expr/lexer.h"

namespace expr {

namespace {

bool is_space(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

bool is_digit(char c) {
    return c >= '0' && c <= '9';
}

bool is_ident_start(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}

bool is_ident_char(char c) {
    return is_ident_start(c) || is_digit(c);
}

} // namespace

std::vector<Token> lex(const std::string& src) {
    std::vector<Token> out;
    std::size_t i = 0;
    const std::size_t n = src.size();

    while (i < n) {
        const char c = src[i];

        if (is_space(c)) {
            ++i;
            continue;
        }

        // Numbers: integers, decimals, exponent notation (1e3, 2.5e-2).
        if (is_digit(c) || (c == '.' && i + 1 < n && is_digit(src[i + 1]))) {
            std::size_t start = i;
            while (i < n && is_digit(src[i])) ++i;
            if (i < n && src[i] == '.') {
                ++i;
                while (i < n && is_digit(src[i])) ++i;
            }
            if (i < n && (src[i] == 'e' || src[i] == 'E')) {
                std::size_t exp = i;
                ++i;
                if (i < n && (src[i] == '+' || src[i] == '-')) ++i;
                if (i < n && is_digit(src[i])) {
                    while (i < n && is_digit(src[i])) ++i;
                } else {
                    i = exp;  // "1e" -> number ends at 'e'; 'e' lexes as identifier.
                }
            }
            out.push_back({TokenKind::Number, src.substr(start, i - start), start});
            continue;
        }

        if (is_ident_start(c)) {
            std::size_t start = i;
            while (i < n && is_ident_char(src[i])) ++i;
            out.push_back({TokenKind::Identifier, src.substr(start, i - start), start});
            continue;
        }

        TokenKind kind;
        switch (c) {
            case '+': kind = TokenKind::Plus;    break;
            case '-': kind = TokenKind::Minus;   break;
            case '*': kind = TokenKind::Star;    break;
            case '/': kind = TokenKind::Slash;   break;
            case '^': kind = TokenKind::Caret;   break;
            case '%': kind = TokenKind::Percent; break;
            case '(': kind = TokenKind::LParen;  break;
            case ')': kind = TokenKind::RParen;  break;
            case ',': kind = TokenKind::Comma;   break;
            default:
                out.push_back({TokenKind::Error, std::string(1, c), i});
                ++i;
                continue;
        }
        out.push_back({kind, std::string(1, c), i});
        ++i;
    }

    out.push_back({TokenKind::End, "", n});
    return out;
}

} // namespace expr
