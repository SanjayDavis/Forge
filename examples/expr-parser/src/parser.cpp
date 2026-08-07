// Proof #3: C++ expression parser — parser implementation.
//
// Grammar (precedence climbing, Pratt-style):
//   expression := unary ( ('+'|'-'|'*'|'/'|'%'|'^') unary )*
//   unary      := ('-'|'+') unary | primary
//   primary    := NUMBER | IDENTIFIER | IDENTIFIER '(' args ')' | '(' expression ')'
//
// Precedence:  + -  (10, left)  <  * / %  (20, left)  <  ^  (30, RIGHT)
// Unary binds tighter than binary, but looser than '^' on its right operand,
// so -2^2 parses as -(2^2).
#include "expr/parser.h"

#include <cstdlib>
#include <string>

#include "expr/error.h"

namespace expr {

namespace {

struct Parser {
    const std::vector<Token>& toks;
    std::size_t i = 0;

    const Token& peek() const { return toks[i]; }
    const Token& advance() { return toks[i++]; }
    bool at(TokenKind k) const { return peek().kind == k; }

    void expect(TokenKind k, const char* what) {
        if (peek().kind != k) {
            throw ParseError(
                std::string("expected ") + what + " but got " +
                    token_kind_name(peek().kind),
                peek().pos);
        }
        advance();
    }

    // Precedence of a binary operator; 0 means "not a binary op".
    int bin_prec(TokenKind k, bool& right_assoc) const {
        right_assoc = false;
        switch (k) {
            case TokenKind::Plus:
            case TokenKind::Minus:       return 10;
            case TokenKind::Star:
            case TokenKind::Slash:
            case TokenKind::Percent:     return 20;
            case TokenKind::Caret:       right_assoc = true; return 30;
            default:                     return 0;
        }
    }

    std::shared_ptr<Node> parse_expr(int min_prec = 0) {
        std::shared_ptr<Node> lhs = parse_prefix();
        for (;;) {
            bool right_assoc = false;
            const int prec = bin_prec(peek().kind, right_assoc);
            if (prec == 0 || prec < min_prec) break;
            const Token op = advance();
            const int next_min = right_assoc ? prec : prec + 1;
            lhs = make_binary(op.text[0], lhs, parse_expr(next_min));
        }
        return lhs;
    }

    // Unary operators live INSIDE the precedence loop at level 25: tighter
    // than * / % (20) but looser than ^ (30), so -2^2 parses as -(2^2).
    std::shared_ptr<Node> parse_prefix() {
        if (at(TokenKind::Minus) || at(TokenKind::Plus)) {
            const Token op = advance();
            return make_unary(op.text[0], parse_expr(25));
        }
        return parse_primary();
    }

    std::shared_ptr<Node> parse_primary() {
        const Token t = peek();
        switch (t.kind) {
            case TokenKind::Number:
                advance();
                return make_number(std::strtod(t.text.c_str(), nullptr));

            case TokenKind::Identifier:
                advance();
                if (at(TokenKind::LParen)) {
                    advance();  // consume '('
                    std::vector<std::shared_ptr<Node>> args;
                    if (!at(TokenKind::RParen)) {
                        args.push_back(parse_expr());
                        while (at(TokenKind::Comma)) {
                            advance();
                            args.push_back(parse_expr());
                        }
                    }
                    expect(TokenKind::RParen, "')' after call arguments");
                    return make_call(t.text, std::move(args));
                }
                return make_variable(t.text);

            case TokenKind::LParen: {
                advance();
                std::shared_ptr<Node> inner = parse_expr();
                expect(TokenKind::RParen, "')'");
                return inner;
            }

            case TokenKind::Error:
                advance();
                throw ParseError("unexpected character '" + t.text + "'", t.pos);

            case TokenKind::End:
                throw ParseError("unexpected end of input", t.pos);

            default:
                throw ParseError(
                    std::string("unexpected token ") + token_kind_name(t.kind),
                    t.pos);
        }
    }

    void finish() {
        if (!at(TokenKind::End)) {
            throw ParseError("unexpected trailing token '" + peek().text + "'",
                             peek().pos);
        }
    }
};

} // namespace

std::shared_ptr<Node> parse(const std::vector<Token>& tokens) {
    Parser p{tokens};
    std::shared_ptr<Node> node = p.parse_expr();
    p.finish();
    return node;
}

} // namespace expr
