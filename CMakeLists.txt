cmake_minimum_required(VERSION 3.15)

file (STRINGS "VERSION" GRAFANA_VERSION)

project(
    grafana
    VERSION "${GRAFANA_VERSION}"
    DESCRIPTION "Featuremine graphics"
    HOMEPAGE_URL "https://www.featuremine.com"
)

set(Subproject_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
find_package(Subproject REQUIRED)

add_subproject(
    NAME yamal
    VERSION "7.2.21"
    GIT_REVISION "v7.2.21"
    GIT_URL "https://github.com/featuremine/yamal.git"
    TARGETS fmc++ ytp yamal-run yamal-stats
)
add_subproject(
    NAME bulldozer
    VERSION "0.0.5"
    GIT_REVISION "v0.0.5"
    GIT_URL "https://github.com/featuremine/bulldozer.git"
    TARGETS bulldozer
)


add_custom_target(dummy ALL DEPENDS yamal-run yamal-stats bulldozer)