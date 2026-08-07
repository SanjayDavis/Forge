// Proof #3: C++ expression parser — lexer unit tests.
#include <cstdio>
#include <string>
#include <vector>

#include "expr/lexer.h"

namespace {

struct Case {
    std::string input;
    std::vector<expr::TokenKind> kinds;  // expected kinds in order
};

const std::vector<Case> kCases = {
    {"2+3*4", {expr::TokenKind::Number, expr::TokenKind::Plus,
               expr::TokenKind::Number, expr::TokenKind::Star,
               expr::TokenKind::Number, expr::TokenKind::End}},
    {"1.5", {expr::TokenKind::Number, expr::TokenKind::End}},
    {"1e3", {expr::TokenKind::Number, expr::TokenKind::End}},
    {"2.5e-2", {expr::TokenKind::Number, expr::TokenKind::End}},
    {"1E5", {expr::TokenKind::Number, expr::TokenKind::End}},
    {"abc_1", {expr::TokenKind::Identifier, expr::TokenKind::End}},
    {"(x, y)", {expr::TokenKind::LParen, expr::TokenKind::Identifier,
                expr::TokenKind::Comma, expr::TokenKind::Identifier,
                expr::TokenKind::RParen, expr::TokenKind::End}},
    {"^ %", {expr::TokenKind::Caret, expr::TokenKind::Percent,
             expr::TokenKind::End}},
    {"  12  +  3 ", {expr::TokenKind::Number, expr::TokenKind::Plus,
                     expr::TokenKind::Number, expr::TokenKind::End}},
    {"", {expr::TokenKind::End}},
    {"2$3", {expr::TokenKind::Number, expr::TokenKind::Error,
             expr::TokenKind::Number, expr::TokenKind::End}},
    {"@", {expr::TokenKind::Error, expr::TokenKind::End}},
};

} // namespace

int run_lexer_tests() {
    int passed = 0;
    int failed = 0;

    for (const Case& c : kCases) {
        std::vector<expr::Token> toks = expr::lex(c.input);
        if (toks.size() != c.kinds.size()) {
            std::printf("FAIL  lex(%s): %zu tokens, expected %zu\n",
                        c.input.c_str(), toks.size(), c.kinds.size());
            ++failed;
            continue;
        }
        bool ok = true;
        for (std::size_t i = 0; i < toks.size(); ++i) {
            if (toks[i].kind != c.kinds[i]) {
                std::printf("FAIL  lex(%s): token %zu is %s, expected %s\n",
                            c.input.c_str(), i,
                            expr::token_kind_name(toks[i].kind),
                            expr::token_kind_name(c.kinds[i]));
                ok = false;
                break;
            }
        }
        if (ok) ++passed;
        else ++failed;
    }

    // Position check: error token must point at the offending character.
    std::vector<expr::Token> toks = expr::lex("2$3");
    bool pos_ok = toks[1].pos == 1;
    if (pos_ok) ++passed; else {
        std::printf("FAIL  lex(\"2$3\"): error token pos = %zu, expected 1\n", toks[1].pos);
        ++failed;
    }

    std::printf("lexer tests: %d passed, %d failed\n", passed, failed);
    return failed == 0 ? 0 : 1;
}
