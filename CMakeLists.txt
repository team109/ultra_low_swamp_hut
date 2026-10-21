cmake_minimum_required(VERSION 3.20)
project(ultra_low_hut LANGUAGES C CXX)

option(HUT_SPARSE_DENSITY_CACHE "Evaluate terrain interpolation nodes on demand" ON)
option(HUT_COMPILED_LAYOUT_PROBES "Cache layout-specific terrain probe plans" ON)
if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -ffp-contract=off -fwrapv")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -ffp-contract=off")
set(REFERENCE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/external" CACHE PATH "Source dependencies")
set(LY "${REFERENCE_ROOT}/LowYSwampHut/lysh-c/src")
set(GENERATED "${CMAKE_CURRENT_BINARY_DIR}/generated")
find_package(Python3 REQUIRED COMPONENTS Interpreter)

file(GLOB LY_SOURCES "${LY}/*.c")
list(FILTER LY_SOURCES EXCLUDE REGEX "/(main|jni_bridge|eval|phase2)\\.c$")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_screen_eval.py")
execute_process(
    COMMAND ${Python3_EXECUTABLE}
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_screen_eval.py"
        "${LY}/eval.c" "${GENERATED}/eval_screen.c"
    COMMAND_ERROR_IS_FATAL ANY)
list(APPEND LY_SOURCES "${GENERATED}/eval_screen.c")

# Expose post-carver blocks for the mineshaft boundary-fluid checks.
file(READ "${LY}/phase2.c" PHASE2_SOURCE)
string(APPEND PHASE2_SOURCE "
lysh_block_state ms_post_carver_block(lysh_phase2 *p2, int x, int y, int z) {
    if (y < -64 || y >= 320) return LYSH_BLOCK_AIR;
    lysh_phase2_ensure_chunk(p2, x, z);
    const uint8_t *cells = carve_cells_for(p2, x >> 4, z >> 4);
    return carved_state_at(p2, cells, x, y, z);
}
")
file(WRITE "${GENERATED}/phase2_structures.c" "${PHASE2_SOURCE}")
if(HUT_SPARSE_DENSITY_CACHE)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_sparse_phase2.py")
    execute_process(
        COMMAND ${Python3_EXECUTABLE}
            "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_sparse_phase2.py"
            "${GENERATED}/phase2_structures.c" "${GENERATED}/phase2_structures.c"
        COMMAND_ERROR_IS_FATAL ANY)
endif()

add_library(lysh STATIC ${LY_SOURCES} "${GENERATED}/phase2_structures.c")
target_compile_options(lysh PRIVATE -include stddef.h)
target_include_directories(lysh PUBLIC "${LY}")
add_library(mcsearch SHARED native/hut_reference.cpp)
if(HUT_COMPILED_LAYOUT_PROBES)
    target_compile_definitions(mcsearch PRIVATE HUT_COMPILED_LAYOUT_PROBES)
endif()
target_link_libraries(mcsearch PRIVATE lysh m pthread)

add_custom_target(hut_version_table
    COMMAND ${Python3_EXECUTABLE}
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_hut_versions.py"
    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/data/versions/hut.json"
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_hut_versions.py"
    BYPRODUCTS "${CMAKE_CURRENT_SOURCE_DIR}/native/hut_versions.generated.h")
add_dependencies(mcsearch hut_version_table)
