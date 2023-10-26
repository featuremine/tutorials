#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

set(WHEEL_FILES "")

function(wheel_copy_file)
    cmake_parse_arguments(
        ARG
        ""
        "SRC;DST"
        ""
        ${ARGN}
    )
    set(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/dist/${ARG_DST}")
    cmake_path(RELATIVE_PATH OUTPUT BASE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}" OUTPUT_VARIABLE OUTPUT_REL)
    set(DEST_PATH "${CMAKE_CURRENT_BINARY_DIR}/${OUTPUT_REL}")
    cmake_path(GET DEST_PATH PARENT_PATH DEST_BASE)
    message(WARNING "CREATING DIRECTORY ${DEST_BASE}")
    add_custom_command(
        OUTPUT "${OUTPUT}"
        DEPENDS "${PROJECT_SOURCE_DIR}/python/${ARG_SRC}"
        COMMAND
        ${CMAKE_COMMAND} -E make_directory
        "${DEST_BASE}"
        COMMAND ${CMAKE_COMMAND} -E copy
        "${PROJECT_SOURCE_DIR}/python/${ARG_SRC}"
        "${OUTPUT}"
    )
    list(APPEND WHEEL_FILES "${OUTPUT}")
    set(WHEEL_FILES ${WHEEL_FILES} PARENT_SCOPE)
endfunction()

wheel_copy_file(SRC "src/__init__.py" DST "tutorials/__init__.py")
wheel_copy_file(SRC "tests/__init__.py" DST "tutorials/tests/__init__.py")
wheel_copy_file(SRC "tests/marketdata02consolidated.py" DST "tutorials/tests/marketdata02consolidated.py")
wheel_copy_file(SRC "scripts/test-tutorials-python" DST "scripts/test-tutorials-python")

if(CMAKE_BUILD_TYPE MATCHES DEBUG)
    set(DEBUG_FLAG "--debug")
endif()

if(BUILD_WHEEL)
    file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}-py")
    find_program(PYTHON3_BIN "python3")
    add_custom_command(
        OUTPUT "${CMAKE_BINARY_DIR}/output/tutorials-${PROJECT_VERSION}-py3-none-${PYTHON_PLATFORM}.whl"

        COMMAND
        "${PYTHON3_BIN}" "${CMAKE_CURRENT_SOURCE_DIR}/setup.py"

        "build"
        "--build-base=${CMAKE_CURRENT_BINARY_DIR}/buildwheel"
        "--build-lib=${CMAKE_CURRENT_BINARY_DIR}/buildwheel/lib"
        ${DEBUG_FLAG}

        "egg_info"
        "--egg-base" "${CMAKE_CURRENT_BINARY_DIR}"

        "bdist_wheel"
        "--bdist-dir=${CMAKE_CURRENT_BINARY_DIR}/bdist"
        "--dist-dir=${CMAKE_BINARY_DIR}/output"

        "--plat-name=${PYTHON_PLATFORM}"
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/dist

        DEPENDS ${WHEEL_FILES}
    )

    add_custom_command(
        OUTPUT "${CMAKE_CURRENT_BINARY_DIR}-py/tutorials.egg-info/SOURCES.txt"
    
        COMMAND
        "${PYTHON3_BIN}" "${CMAKE_CURRENT_SOURCE_DIR}/setup.py"

        "build_scripts"
        "--executable=${PYTHON3_BIN}"

        "egg_info"
        "--egg-base" "${CMAKE_CURRENT_BINARY_DIR}-py"

        "build"
        "--build-base=${CMAKE_CURRENT_BINARY_DIR}/build"
        "--build-lib=${CMAKE_CURRENT_BINARY_DIR}/build/lib"
        "--build-scripts=${CMAKE_CURRENT_BINARY_DIR}/build/scripts"
        ${DEBUG_FLAG}

        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/dist

        DEPENDS ${WHEEL_FILES}
    )
    add_custom_target(
        tutorials-whl ALL
        DEPENDS "${CMAKE_BINARY_DIR}/output/tutorials-${PROJECT_VERSION}-py3-none-${PYTHON_PLATFORM}.whl"
    )
    add_custom_target(
        tutorials-py ALL
        DEPENDS "${CMAKE_CURRENT_BINARY_DIR}-py/tutorials.egg-info/SOURCES.txt"
    )
    set(WHEEL_tutorials_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}" CACHE INTERNAL "Wheel path for tutorials" FORCE)
    set(WHEEL_tutorials_SCRIPTS "${CMAKE_CURRENT_BINARY_DIR}" CACHE INTERNAL "Wheel script path for tutorials" FORCE)
endif()

if(BUILD_TESTING)
    enable_testing()
    if(TEST_EXTENSIONS)
        if(BUILD_WHEEL)
            set(WheelPackage_DIR "${PROJECT_SOURCE_DIR}/cmake")
            find_package(WheelPackage REQUIRED)
            test_python_package(
                NAME tutorials_py
                PACKAGE tutorials
                TIMEOUT 100
                TEST "test-tutorials-python"
                DEPENDS tutorials-py
            )
        endif()
    endif()
endif()
