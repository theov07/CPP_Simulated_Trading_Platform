cmake_minimum_required(VERSION 3.15)
project(TradingPlatform CXX)

if (POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(TRADING_CORE_SOURCES
    src/MarketDataFeed.cpp
    src/OrderBook.cpp
    src/MatchingEngine.cpp
    src/Strategy.cpp
    src/StrategyEngine.cpp
    src/Portfolio.cpp
    src/Reporting.cpp
    src/RiskMetrics.cpp
    src/CsvWriter.cpp
    src/BacktestLogger.cpp
)

function(enable_project_warnings target_name)
    if (MSVC)
        target_compile_options(${target_name} PRIVATE /W4)
    else()
        target_compile_options(${target_name} PRIVATE -Wall -Wextra -Wpedantic)
    endif()
endfunction()

add_library(trading_core ${TRADING_CORE_SOURCES})
target_include_directories(trading_core PUBLIC include)
target_compile_features(trading_core PUBLIC cxx_std_17)
enable_project_warnings(trading_core)

add_executable(trading_sim src/main.cpp)
target_link_libraries(trading_sim PRIVATE trading_core)
enable_project_warnings(trading_sim)

enable_testing()
include(GoogleTest)
include(FetchContent)

set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
)
FetchContent_MakeAvailable(googletest)

add_executable(trading_tests tests/test_core.cpp)
target_link_libraries(trading_tests PRIVATE trading_core GTest::gtest_main)
enable_project_warnings(trading_tests)
gtest_discover_tests(trading_tests)
