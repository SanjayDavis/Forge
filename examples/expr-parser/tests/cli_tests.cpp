// Proof #3: C++ expression parser — CLI end-to-end tests.
// Runs the built ./expr binary and checks stdout, stderr, and exit codes.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct Case {
    std::string args;      // expression (or "" for REPL mode)
    std::string want;      // expected stdout (exact, after trim) or prefix
    bool prefix;           // true: stdout must START with want
    int want_exit;
    bool stderr_check;
    std::string stderr_frag;
};

const std::vector<Case> kCases = {
    {"2+3", "5", false, 0, false, ""},
    {"10-3-2", "5", false, 0, false, ""},
    {"3*4+5", "17", false, 0, false, ""},
    {"2^3^2", "512", false, 0, false, ""},
    {"sqrt(4)", "2", false, 0, false, ""},
    {"pi", "3.14159265359", true, 0, false, ""},
    {"2.5e-1", "0.25", false, 0, false, ""},
    {"1/0", "", false, 1, true, "division by zero"},
    {"2+", "", false, 1, true, "column"},
    {"(", "", false, 1, true, "column"},
    {"zzz", "", false, 1, true, "unknown variable"},
};

std::string trim(const std::string& s) {
    std::string t = s;
    while (!t.empty() && (t.back() == '\n' || t.back() == '\r')) t.pop_back();
    return t;
}

std::string read_file(const std::string& path) {
    std::ifstream f(path.c_str());
    std::stringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

} // namespace

int run_cli_tests() {
    int passed = 0;
    int failed = 0;

    for (const Case& c : kCases) {
        const std::string cmd =
            "expr \"" + c.args + "\" > cli_out.txt 2> cli_err.txt";
        const int rc = std::system(cmd.c_str());
        const std::string out = trim(read_file("cli_out.txt"));
        const std::string err = read_file("cli_err.txt");

        bool ok = true;
        if (rc != c.want_exit) {
            std::printf("FAIL  expr(%s): exit %d, expected %d\n", c.args.c_str(),
                        rc, c.want_exit);
            ok = false;
        }
        if (c.prefix) {
            if (out.compare(0, c.want.size(), c.want) != 0) {
                std::printf("FAIL  expr(%s): stdout '%s' lacks prefix '%s'\n",
                            c.args.c_str(), out.c_str(), c.want.c_str());
                ok = false;
            }
        } else if (out != c.want) {
            std::printf("FAIL  expr(%s): stdout '%s', expected '%s'\n",
                        c.args.c_str(), out.c_str(), c.want.c_str());
            ok = false;
        }
        if (c.stderr_check &&
            err.find(c.stderr_frag) == std::string::npos) {
            std::printf("FAIL  expr(%s): stderr lacks '%s' (got: %s)\n",
                        c.args.c_str(), c.stderr_frag.c_str(), err.c_str());
            ok = false;
        }

        if (ok) ++passed; else ++failed;
    }

    // REPL mode via piped stdin: "2+3" then quit.
    {
        std::ofstream in("repl_in.txt");
        in << "2+3\nsqrt(9)\nquit\n";
        in.close();
        const int rc =
            std::system("expr < repl_in.txt > repl_out.txt 2> repl_err.txt");
        const std::string out = read_file("repl_out.txt");
        if (rc == 0 && out.find("5") != std::string::npos &&
            out.find("3") != std::string::npos) {
            ++passed;
        } else {
            std::printf("FAIL  REPL piped input (rc=%d, out=%s)\n", rc,
                        out.c_str());
            ++failed;
        }
    }

    // :ast debug command.
    {
        std::ofstream in("repl_in.txt");
        in << ":ast 2+3*4\nquit\n";
        in.close();
        std::system("expr < repl_in.txt > repl_out.txt 2> repl_err.txt");
        const std::string out = read_file("repl_out.txt");
        if (out.find("(+ 2 (* 3 4))") != std::string::npos) {
            ++passed;
        } else {
            std::printf("FAIL  :ast command (out=%s)\n", out.c_str());
            ++failed;
        }
    }

    std::remove("cli_out.txt");
    std::remove("cli_err.txt");
    std::remove("repl_in.txt");
    std::remove("repl_out.txt");
    std::remove("repl_err.txt");

    std::printf("cli tests: %d passed, %d failed\n", passed, failed);
    return failed == 0 ? 0 : 1;
}
