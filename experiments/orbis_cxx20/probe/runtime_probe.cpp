// SPDX-License-Identifier: GPL-2.0-or-later
// Runs real C++ library operations. No replacement synchronization or HLE stubs.
#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <bit>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <latch>
#include <limits>
#include <locale>
#include <mutex>
#include <random>
#include <ranges>
#include <span>
#include <sstream>
#include <stdexcept>
#include <stop_token>
#include <string>
#include <thread>

namespace {
unsigned checks = 0;
const char* stage = "entry";
#ifdef SO_PLATFORM_ORBIS
constexpr const char* result_path = "/data/orbis-cxx20.json";
constexpr const char* stage_path = "/data/orbis-cxx20-stage.txt";
constexpr const char* work_path = "/data/orbis-cxx20-files";
#else
constexpr const char* result_path = "orbis-cxx20.json";
constexpr const char* stage_path = "orbis-cxx20-stage.txt";
constexpr const char* work_path = "orbis-cxx20-files";
#endif
void Require(bool value, const char* what) {
    ++checks;
    if (!value) {
        std::fprintf(stderr, "FAIL [%s]: %s\n", stage, what);
        std::fflush(stderr);
        std::abort();
    }
}
void Stage(const char* name) {
    stage = name;
    std::fprintf(stderr, "[cxx20] %s\n", name);
    std::fflush(stderr);
    FILE* file = std::fopen(stage_path, "w");
    Require(file != nullptr, "open progress report");
    const bool written = std::fprintf(file, "%s\n", name) > 0;
    const bool closed = std::fclose(file) == 0;
    Require(written && closed, "write progress report");
}
std::atomic<unsigned> tls_destroyed{0};
struct ThreadState {
    unsigned value = 0;
    ~ThreadState() { tls_destroyed.fetch_add(1); }
};
thread_local ThreadState tls;
std::atomic<unsigned> unwound{0};
struct Guard { ~Guard() { unwound.fetch_add(1); } };
struct Parent { virtual ~Parent() = default; };
struct Child : Parent { unsigned value = 42; };
__attribute__((noinline)) void Throw() {
    Guard guard;
    throw std::runtime_error("orbis exception proof");
}
void MathAndLocale() {
    Stage("math_locale_ranges");
    const auto nan = std::numeric_limits<double>::quiet_NaN();
    const auto inf = std::numeric_limits<double>::infinity();
    const auto tiny = std::numeric_limits<float>::denorm_min();
    Require(std::isnan(nan) && !std::isnan(42.0), "NaN classification");
    Require(std::isinf(inf) && !std::isfinite(inf) && std::isfinite(42), "infinity and integral overloads");
    Require(std::signbit(-0.0) && !std::signbit(0.0), "signed zero");
    Require(std::fpclassify(tiny) == FP_SUBNORMAL && !std::isnormal(tiny), "subnormal float");
    Require(std::isunordered(nan, 1.0) && !std::isless(nan, 1.0), "unordered comparisons");
    Require(std::bit_cast<unsigned>(1.0f) == 0x3f800000U, "bit_cast");
    std::array<int, 4> numbers{4, 1, 3, 2};
    std::ranges::sort(numbers);
    std::span<int> view(numbers);
    Require(view.front() == 1 && view.back() == 4, "ranges and span");
    const auto& facet = std::use_facet<std::ctype<char>>(std::locale::classic());
    Require(facet.toupper('a') == 'A' && facet.tolower('Z') == 'z', "musl locale char case");
    const auto& wide = std::use_facet<std::ctype<wchar_t>>(std::locale::classic());
    Require(wide.toupper(L'a') == L'A' && wide.tolower(L'Z') == L'z', "musl locale wide case");
    std::stringstream text;
    text.imbue(std::locale::classic());
    text << 42 << ' ' << 1.5;
    int n = 0; double f = 0;
    text >> n >> f;
    Require(n == 42 && f == 1.5, "locale stream roundtrip");
}
void Exceptions() {
    Stage("exception_unwind_rtti");
    bool caught = false;
    try { Throw(); }
    catch (const std::runtime_error& error) {
        caught = std::string(error.what()) == "orbis exception proof";
    }
    Require(caught && unwound.load() == 1, "exception type, message and stack destructor");
    Child derived;
    Parent* base = &derived;
    Require(dynamic_cast<Child*>(base) == &derived, "RTTI dynamic cast");
}
void AtomicAndTls() {
    Stage("threads_atomic_ref_barrier_tls");
    alignas(std::atomic_ref<unsigned>::required_alignment) unsigned counter = 0;
    std::barrier rendezvous(3);
    std::array<std::jthread, 2> workers;
    std::array<unsigned, 2> seen{};
    for (unsigned i=0; i<2; ++i) workers[i] = std::jthread([&, i] {
        tls.value = i + 100;
        for (unsigned phase=0; phase<8; ++phase) {
            rendezvous.arrive_and_wait();
            for (unsigned j=0; j<256; ++j) std::atomic_ref<unsigned>(counter).fetch_add(1);
            rendezvous.arrive_and_wait();
        }
        seen[i] = tls.value;
    });
    for (unsigned phase=0; phase<8; ++phase) {
        rendezvous.arrive_and_wait();
        rendezvous.arrive_and_wait();
    }
    for (auto& worker : workers) worker.join();
    Require(counter == 4096, "atomic_ref concurrent increments");
    Require(seen[0] == 100 && seen[1] == 101, "independent native TLS state");
    Require(tls_destroyed.load() == 2, "thread_local destructors on join");
    Stage("atomic_wait_notify");
    std::atomic<unsigned> event{0}; std::latch ready(1);
    unsigned observed = 0;
    std::jthread waiter([&] {
        ready.count_down(); event.wait(0, std::memory_order_acquire);
        observed = event.load(std::memory_order_acquire);
    });
    ready.wait();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    event.store(7, std::memory_order_release); event.notify_one();
    waiter.join(); Require(observed == 7, "atomic wait completes after notification");
}
void StopAndClock() {
    Stage("jthread_stop_aware_wait");
    std::mutex lock; std::condition_variable_any cv; std::latch ready(1);
    bool stopped = false;
    std::atomic<unsigned> callbacks{0};
    std::jthread worker([&](std::stop_token token) {
        std::stop_callback callback(token, [&] { callbacks.fetch_add(1); });
        std::unique_lock guard(lock); ready.count_down();
        const bool predicate = cv.wait(guard, token, [] { return false; });
        stopped = !predicate && token.stop_requested();
    });
    ready.wait();
    const auto start = std::chrono::steady_clock::now();
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    Require(worker.request_stop(), "request_stop changes state");
    worker.join();
    const auto elapsed = std::chrono::steady_clock::now() - start;
    Require(stopped && callbacks.load() == 1, "stop callback and condition-variable wakeup");
    Require(elapsed >= std::chrono::milliseconds(10) && elapsed < std::chrono::seconds(5), "steady_clock duration");
    std::latch destructor_ready(1); bool destructor_stopped = false;
    {
        std::jthread scoped([&](std::stop_token token) {
            std::unique_lock guard(lock); destructor_ready.count_down();
            cv.wait(guard, token, [] { return false; });
            destructor_stopped = token.stop_requested();
        });
        destructor_ready.wait();
    }
    Require(destructor_stopped, "jthread destructor requests stop and joins");
}
void Files() {
    Stage("filesystem_roundtrip");
    namespace fs = std::filesystem;
    const fs::path dir(work_path);
    Require(!fs::exists(dir), "fresh filesystem test directory");
    Require(fs::create_directory(dir), "create_directory");
    {
        std::ofstream output(dir/"a.txt");
        output << "orbis-cxx20\n";
        output.close(); Require(!output.fail(), "ofstream write and close");
    }
    fs::rename(dir/"a.txt", dir/"b.txt");
    std::string line;
    { std::ifstream input(dir/"b.txt"); std::getline(input, line); }
    Require(line == "orbis-cxx20", "rename/read");
    std::error_code size_error;
    const auto size = fs::file_size(dir/"b.txt", size_error);
    std::fprintf(stdout, "[cxx20] filesystem size=%llu ec=%d line_len=%zu\n",
                 static_cast<unsigned long long>(size), size_error.value(), line.size());
    std::fflush(stdout);
    Require(!size_error && size == 12, "file_size");
    Require(fs::remove(dir/"b.txt") && fs::remove(dir), "file/directory removal");
    Stage("random_device_reads");
    std::random_device random;
    volatile unsigned sink = 0;
    for (unsigned i=0; i<4; ++i) sink = random();
    (void)sink; // This proves successful reads, not statistical/cryptographic quality.
}
}
int main() {
    Stage("entry");
    MathAndLocale(); Exceptions(); AtomicAndTls(); StopAndClock(); Files();
    Stage("complete");
    char report[1024];
    const int count = std::snprintf(report, sizeof(report),
        "{\"test\":\"orbis_modern_cxx_runtime\",\"passed\":true,\"checks\":%u,"
        "\"libcpp_version\":%u,\"math_locale_ranges\":true,\"exception_unwind_rtti\":true,"
        "\"atomic_ref_total\":4096,\"tls_destructors\":2,\"barrier_phases\":8,"
        "\"atomic_wait_notify\":true,\"jthread_stop_wait\":true,\"filesystem\":true,"
        "\"random_reads\":4,\"full_core_linked\":false,\"game_tested\":false}\n",
        checks,
#ifdef _LIBCPP_VERSION
        static_cast<unsigned>(_LIBCPP_VERSION)
#else
        0U
#endif
    );
    Require(count>0 && static_cast<std::size_t>(count)<sizeof(report), "result fits");
    FILE* file = std::fopen(result_path, "w");
    Require(file != nullptr, "open result");
    const bool written = std::fputs(report, file) >= 0;
    const bool closed = std::fclose(file) == 0;
    Require(written && closed, "save result");
    std::fputs(report, stdout);
    return 0;
}
